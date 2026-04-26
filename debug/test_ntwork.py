# -*- coding: utf-8 -*-
import sys
import ntwork

wework = ntwork.WeWork()

# 打开pc企业微信, smart: 是否管理已经登录的企业微信
wework.open(smart=False)

# 等待登录
wework.wait_login()

# 向文件助手发送一条消息
wework.send_text(conversation_id="FILEASSIST", content="hello, NtWork")

try:
    while True:
        pass
except KeyboardInterrupt:
    ntwork.exit_()
    sys.exit()