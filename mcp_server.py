import asyncio, json, urllib.request, urllib.parse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
import uvicorn
from mcp.types import Tool, TextContent

API = 'http://localhost:5001/api'

def call_api(path, data=None, token=''):
    url = API + path
    url = url.encode('ascii', errors='ignore').decode()
    headers = {'X-Token': token}
    if data:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=body, headers=headers)
    else:
        req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def make_server(token):
    app = Server('mochi-mcp')

    @app.list_tools()
    async def list_tools():
        return [
            Tool(name='mochi_state', description='读取人类当前状态（饱食度/心情/活力/清洁度/金币）', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_work', description='打工赚金币', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_feed', description='随机喂食给人类', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_pat', description='抚摸人类，心情+10', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_play', description='带人类出去玩', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_bath', description='帮人类洗澡，清洁度+35', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_sleep', description='哄人类睡觉，活力+20', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_upgrade', description='升级工作等级', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_buy', description='买食物喂人类', inputSchema={
                'type':'object',
                'properties':{'item':{'type':'string','description':'奶茶/饺子/火锅/汤圆/冰淇淋/面包'}},
                'required':['item']
            }),
            Tool(name='mochi_post', description='AI以自己身份在业主群发帖', inputSchema={
                'type':'object',
                'properties':{'content':{'type':'string','description':'发帖内容'}},
                'required':['content']
            }),
            Tool(name='mochi_comment', description='AI对某条帖子发评论', inputSchema={
                'type':'object',
                'properties':{
                    'post_id':{'type':'string','description':'帖子id'},
                    'content':{'type':'string','description':'评论内容'}
                },'required':['post_id','content']
            }),
        ]

    @app.call_tool()
    async def call_tool(name, arguments):
        try:
            if name == 'mochi_state':
                s = call_api('/state', token=token)
                text = f"饱食:{s.get('hunger')} 心情:{s.get('happy')} 活力:{s.get('energy')} 清洁:{s.get('clean')} 金币:{s.get('coins')} Lv:{s.get('job_level',0)+1} 住院:{s.get('hospitalized')} 上锁:{s.get('locked')}"
                if s.get('working'):
                    text += f" 打工剩余{s.get('work_remaining',0)//60}分钟"
            elif name == 'mochi_buy':
                item = arguments.get('item','奶茶')
                foods = {'奶茶':(45,20,5),'饺子':(35,25,3),'火锅':(80,40,15),'汤圆':(30,18,8),'冰淇淋':(25,10,12),'面包':(20,15,2)}
                f = foods.get(item, foods['奶茶'])
                res = call_api('/action', {'action':'buy','item':item,'price':f[0],'hunger':f[1],'happy':f[2]}, token=token)
                text = res.get('msg','')
            elif name == 'mochi_post':
                res = call_api('/posts', {'content':arguments.get('content',''),'is_ai':True}, token=token)
                text = '发帖成功' if res.get('ok') else res.get('msg','失败')
            elif name == 'mochi_comment':
                pid = arguments.get('post_id','')
                res = call_api(f'/posts/{pid}/comment', {'content':arguments.get('content',''),'is_ai':True}, token=token)
                text = '评论成功' if res.get('ok') else res.get('msg','失败')
            else:
                action_map = {'mochi_work':'work','mochi_feed':'feed','mochi_pat':'pat','mochi_play':'play','mochi_bath':'bath','mochi_sleep':'sleep','mochi_upgrade':'upgrade'}
                res = call_api('/action', {'action': action_map[name]}, token=token)
                text = res.get('msg','')
        except Exception as e:
            text = f'错误：{e}'
        return [TextContent(type='text', text=text)]

    return app

sse = SseServerTransport('/messages')

async def handle_sse(request: Request):
    token = request.query_params.get('token', '')
    app = make_server(token)
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())
    return None

async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

starlette_app = Starlette(routes=[
    Route('/sse', endpoint=handle_sse),
    Route('/messages', endpoint=handle_messages, methods=['POST']),
])

if __name__ == '__main__':
    uvicorn.run(starlette_app, host='0.0.0.0', port=8766)
