#!/usr/bin/env node
import { createOpencodeClient } from '@opencode-ai/sdk';
import { pathToFileURL } from 'url';

async function main() {
    const args = process.argv.slice(2);
    const params = {};
    
    for (let i = 0; i < args.length; i += 2) {
        params[args[i].replace('--', '')] = args[i + 1];
    }
    
    const task = params.task || params.instruction;
    const taskId = params['task-id'] || params.taskId || 'default_task';
    const baseUrl = params.url || process.env.OPENCODE_URL || 'http://localhost:4096';
    const workDir = params['work-dir'] || process.cwd();
    const dryRun = params['dry-run'] === 'true';
    const modelProvider = params['model-provider'] || 'opencode';
    const modelId = params['model-id'] || 'minimax-m2.5-free';
    
    console.log(JSON.stringify({
        type: 'info',
        message: 'OpenCode SDK Bridge',
        params: { task, taskId, baseUrl, workDir, dryRun, model: `${modelProvider}/${modelId}` }
    }));
    
    if (dryRun) {
        console.log(JSON.stringify({
            type: 'result',
            success: true,
            status: 'completed',
            message: `[DRY RUN] Would execute: ${task}`
        }));
        process.exit(0);
    }
    
    let client;
    let sessionId;
    
    try {
        client = createOpencodeClient({
            baseUrl: baseUrl,
        });
        
        console.log(JSON.stringify({
            type: 'info',
            message: 'Creating session...',
            workDir
        }));
        
        const session = await client.session.create({
            body: {
                title: `Task: ${taskId}`,
                directory: workDir,
            }
        });
        
        sessionId = session.data.id;
        console.log(JSON.stringify({
            type: 'info',
            message: 'Session created',
            sessionId
        }));
        
        console.log(JSON.stringify({
            type: 'info',
            message: 'Sending task to OpenCode...'
        }));
        
        const result = await client.session.prompt({
            path: { id: sessionId },
            body: {
                model: { providerID: modelProvider, modelID: modelId },
                parts: [{ type: 'text', text: task }],
            },
        });
        
        console.log(JSON.stringify({
            type: 'info',
            message: 'Prompt completed, result type: ' + typeof result
        }));
        
        console.log(JSON.stringify({
            type: 'info',
            message: 'Fetching messages...'
        }));
        
        const messages = await client.session.messages({
            path: { id: sessionId }
        });
        
        console.log(JSON.stringify({
            type: 'info',
            message: 'Messages fetched, count: ' + messages.data.length
        }));
        
        const lastMessage = messages.data[messages.data.length - 1];
        const assistantMessage = lastMessage?.info || {};
        
        const filesCreated = [];
        const filesModified = [];
        const errors = [];
        
        if (lastMessage?.parts) {
            for (const part of lastMessage.parts) {
                if (part.type === 'tool' && part.tool === 'write' && part.state?.status === 'completed') {
                    const filePath = part.state?.metadata?.filepath || part.state?.input?.filePath;
                    if (filePath) {
                        filesCreated.push(filePath);
                    }
                }
                if (part.type === 'tool' && part.state?.status === 'failed') {
                    errors.push(part.state?.output || 'Unknown error');
                }
            }
        }
        
        const success = assistantMessage.finish !== 'error' && errors.length === 0;
        const summary = filesCreated.length > 0 
            ? `Created files: ${filesCreated.join(', ')}`
            : (filesModified.length > 0 ? `Modified files: ${filesModified.join(', ')}` : 'Task completed');
        
        console.log(JSON.stringify({
            type: 'result',
            success,
            status: 'completed',
            summary,
            files_created: filesCreated,
            files_modified: filesModified,
            errors,
            sessionId,
            tokens: assistantMessage.tokens,
            finish: assistantMessage.finish
        }));
        
    } catch (error) {
        console.log(JSON.stringify({
            type: 'error',
            message: error.message,
            stack: error.stack
        }));
        process.exit(1);
    }
}

main().then(() => {
    console.log(JSON.stringify({ type: 'info', message: 'Script completed' }));
}).catch(err => {
    console.log(JSON.stringify({ type: 'error', message: 'Unhandled error: ' + err.message }));
    process.exit(1);
});
