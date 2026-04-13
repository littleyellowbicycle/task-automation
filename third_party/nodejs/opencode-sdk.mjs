#!/usr/bin/env node
import { createOpencodeClient } from "@opencode-ai/sdk";

const baseUrl = process.env.OPENCODE_API_URL || process.env.EXECUTOR_WEB_URL || "http://localhost:4096";
const client = createOpencodeClient({ baseUrl });

async function main() {
  const action = process.argv[2];
  
  try {
    switch (action) {
      case "health": {
        const resp = await fetch(baseUrl + "/global/health", {
          headers: { "Accept": "application/json" },
        });
        const data = await resp.json();
        console.log(JSON.stringify(data));
        break;
      }
      
      case "create-session": {
        const title = process.argv[3] || "Task Automation";
        const result = await client.session.create({ body: { title } });
        console.log(JSON.stringify(result.data));
        break;
      }
      
      case "prompt": {
        const sessionId = process.argv[3];
        const instruction = process.argv[4];
        const modelProvider = process.argv[5] || "";
        const modelId = process.argv[6] || "";
        
        if (!sessionId || !instruction) {
          console.error(JSON.stringify({ error: "Missing sessionId or instruction" }));
          process.exit(1);
        }
        
        const body = {
          parts: [{ type: "text", text: instruction }],
        };
        
        if (modelProvider && modelId) {
          body.model = { providerID: modelProvider, modelID: modelId };
        }
        
        const result = await client.session.prompt({
          path: { id: sessionId },
          body,
        });
        
        console.log(JSON.stringify(result.data));
        break;
      }
      
      case "abort": {
        const sessionId = process.argv[3];
        if (!sessionId) {
          console.error(JSON.stringify({ error: "Missing sessionId" }));
          process.exit(1);
        }
        const result = await client.session.abort({ path: { id: sessionId } });
        console.log(JSON.stringify({ success: result.data }));
        break;
      }
      
      case "get-messages": {
        const sessionId = process.argv[3];
        if (!sessionId) {
          console.error(JSON.stringify({ error: "Missing sessionId" }));
          process.exit(1);
        }
        const result = await client.session.messages({ path: { id: sessionId } });
        console.log(JSON.stringify(result.data));
        break;
      }
      
      case "execute": {
        const instruction = process.argv[3];
        const modelProvider = process.argv[4] || "";
        const modelId = process.argv[5] || "";
        const title = instruction.substring(0, 50);
        
        if (!instruction) {
          console.error(JSON.stringify({ error: "Missing instruction" }));
          process.exit(1);
        }
        
        const sessionResult = await client.session.create({ body: { title } });
        const sessionId = sessionResult.data.id;
        
        const body = {
          parts: [{ type: "text", text: instruction }],
        };
        
        if (modelProvider && modelId) {
          body.model = { providerID: modelProvider, modelID: modelId };
        }
        
        const promptResult = await client.session.prompt({
          path: { id: sessionId },
          body,
        });
        
        console.log(JSON.stringify({
          sessionId,
          ...promptResult.data
        }));
        break;
      }
      
      default:
        console.error(JSON.stringify({ error: `Unknown action: ${action}` }));
        process.exit(1);
    }
  } catch (error) {
    console.error(JSON.stringify({ error: error.message }));
    process.exit(1);
  }
}

main();
