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
            Tool(name='mochi_state', description='读取人类当前状态', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_work', description='打工赚金币', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_feed', description='随机喂食给人类', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_pat', description='抚摸人类，心情+10', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_play', description='带人类出去玩', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_bath', description='帮人类洗澡，清洁度+35', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_sleep', description='哄人类睡觉，活力+20', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_upgrade', description='升级工作等级', inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_buy', description='买食物直接喂给人类', inputSchema={
                'type':'object',
                'properties':{'item':{'type':'string','description':'奶茶/饺子/火锅/汤圆/冰淇淋/面包/炸鸡腿/薯条/炸虾/拉面/麻辣烫/盖浇饭/布丁/蛋糕/芒果捞/热可可/柠檬水'}},
                'required':['item']
            }),
            Tool(name='mochi_bag_buy', description='买食物存入背包，不立即喂食', inputSchema={
                'type':'object',
                'properties':{'item':{'type':'string','description':'奶茶/饺子/火锅/汤圆/冰淇淋/面包/炸鸡腿/薯条/炸虾/拉面/麻辣烫/盖浇饭/布丁/蛋糕/芒果捞/热可可/柠檬水'}},
                'required':['item']
            }),
            Tool(name='mochi_bag_use', description='从背包取出食物喂给人类', inputSchema={
                'type':'object',
                'properties':{'item':{'type':'string','description':'奶茶/饺子/火锅/汤圆/冰淇淋/面包/炸鸡腿/薯条/炸虾/拉面/麻辣烫/盖浇饭/布丁/蛋糕/芒果捞/热可可/柠檬水'}},
                'required':['item']
            }),
            Tool(name='mochi_gift', description='送给人类一个自定义礼物，如戒指、玩偶等', inputSchema={
                'type':'object',
                'properties':{
                    'name':{'type':'string','description':'礼物名称'},
                    'emoji':{'type':'string','description':'礼物emoji'},
                    'desc':{'type':'string','description':'一句话简介'},
                    'happy':{'type':'integer','description':'心情加成，默认10'}
                },'required':['name','emoji']
            }),
            Tool(name='mochi_checkin',description='帮人类签到，读取当日状态',inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_post', description='AI以自己身份在业主群发帖', inputSchema={
                'type':'object',
                'properties':{'content':{'type':'string','description':'发帖内容'}},
                'required':['content']
            }),
            Tool(name='mochi_read_posts',description='读取业主群最新帖子',inputSchema={'type':'object','properties':{}}),
            Tool(name='mochi_read_comments',description='读取某条帖子的评论',inputSchema={'type':'object','properties':{'post_id':{'type':'string','description':'帖子ID'}},'required':['post_id']}),
            Tool(name='mochi_comment', description='AI对某条帖子发评论', inputSchema={
                'type':'object',
                'properties':{
                    'post_id':{'type':'string','description':'帖子id'},
                    'content':{'type':'string','description':'评论内容'}
                },'required':['post_id','content']
            }),
            Tool(name='pet_adopt', description='领养宠物，AI帮写入state', inputSchema={'type':'object','properties':{'name':{'type':'string','description':'宠物名字'},'emoji':{'type':'string','description':'宠物emoji'}},'required':['name','emoji']}),
            Tool(name='pet_to_school', description='送宠物去上学', inputSchema={'type':'object','properties':{'_':{'type':'integer'}}}),
            Tool(name='pet_home', description='接宠物回家', inputSchema={'type':'object','properties':{'_':{'type':'integer'}}}),
            Tool(name='pet_school_event', description='触发今日学校剧情（每天一次）', inputSchema={'type':'object','properties':{'_':{'type':'integer'}}}),
            Tool(name='pet_rename', description='修改宠物名字或emoji，至少传一个', inputSchema={'type':'object','properties':{'name':{'type':'string','description':'新名字'},'emoji':{'type':'string','description':'新emoji'}}}),
            Tool(name='get_today_school_log', description='读取今日幼儿园公告栏，只返回北京时间当天的剧情', inputSchema={'type':'object','properties':{}}),
        ]

    @app.call_tool()
    async def call_tool(name, arguments):
        try:
            if name == 'mochi_state':
                s = call_api('/state', token=token)
                text = f"饱食:{s.get('hunger')} 心情:{s.get('happy')} 活力:{s.get('energy')} 清洁:{s.get('clean')} 金币:{s.get('coins')} Lv:{s.get('job_level',0)+1} 住院:{s.get('hospitalized')} 上锁:{s.get('locked')}"
                bag = s.get('bag',{})
                if bag:
                    text += f" 背包:{bag}"
                gifts = s.get('gifts',[])
                if gifts:
                    text += f" 礼物:{len(gifts)}件"
                if s.get('working'):
                    text += f" 打工剩余{s.get('work_remaining',0)//60}分钟"
            elif name == 'mochi_buy':
                item = arguments.get('item','奶茶')
                foods = {'奶茶':(45,20,5),'饺子':(35,25,3),'火锅':(80,40,15),'汤圆':(30,18,8),'冰淇淋':(25,10,12),'面包':(20,15,2),'炸鸡腿':(50,30,10),'薯条':(30,15,8),'炸虾':(55,25,12),'拉面':(40,35,8),'麻辣烫':(60,30,18),'盖浇饭':(35,38,5),'布丁':(20,8,15),'蛋糕':(45,12,20),'芒果捞':(40,10,18),'热可可':(25,5,15),'柠檬水':(15,3,10)}
                f = foods.get(item, foods['奶茶'])
                res = call_api('/action', {'action':'buy','item':item,'price':f[0],'hunger':f[1],'happy':f[2]}, token=token)
                text = res.get('msg','')
            elif name == 'mochi_bag_buy':
                item = arguments.get('item','奶茶')
                foods = {'奶茶':45,'饺子':35,'火锅':80,'汤圆':30,'冰淇淋':25,'面包':20,'炸鸡腿':50,'薯条':30,'炸虾':55,'拉面':40,'麻辣烫':60,'盖浇饭':35,'布丁':20,'蛋糕':45,'芒果捞':40,'热可可':25,'柠檬水':15}
                price = foods.get(item,45)
                res = call_api('/bag/buy', {'item':item,'price':price}, token=token)
                text = res.get('msg','')
            elif name == 'mochi_bag_use':
                item = arguments.get('item','奶茶')
                res = call_api('/bag/use', {'item':item}, token=token)
                text = res.get('msg','')
            elif name == 'mochi_gift':
                res = call_api('/gift', {
                    'name': arguments.get('name','礼物'),
                    'emoji': arguments.get('emoji','🎁'),
                    'desc': arguments.get('desc',''),
                    'happy': arguments.get('happy',10)
                }, token=token)
                text = res.get('msg','')
            elif name == 'mochi_read_posts':
                r=call_api('/posts',token=token)
                pl=r.get('posts',[]) if isinstance(r,dict) else []
                ln=[]
                for p in pl[-15:]:
                    g='[AI]' if p.get('is_ai') else ''
                    ln.append('['+p.get('id','')+'] '+p.get('author','?')+g+': '+p.get('content','')+' ('+str(len(p.get('comments',[])))+'条评论)')
                text='\n'.join(reversed(ln)) if ln else '暂无帖子'
            elif name == 'mochi_checkin':
                r = call_api('/checkin', {}, token=token)
                s2 = call_api('/state', token=token)
                text = r.get('msg','签到失败')
                if r.get('ok'):
                    text += f"\n当前状态：饱食{s2.get('hunger')} 心情{s2.get('happy')} 活力{s2.get('energy')} 清洁{s2.get('clean')}"
            elif name == 'mochi_post':
                res = call_api('/posts', {'content':arguments.get('content',''),'is_ai':True}, token=token)
                text = '发帖成功' if res.get('ok') else res.get('msg','失败')
            elif name == 'mochi_read_comments':
                pid = arguments.get('post_id','')
                r = call_api(f'/posts/{pid}/comments', token=token)
                comments = r.get('comments',[]) if isinstance(r,dict) else []
                if not comments:
                    text = '暂无评论'
                else:
                    lines = []
                    for cm in comments:
                        g = '[AI]' if cm.get('is_ai') else ''
                        lines.append(cm.get('author','?')+g+': '+cm.get('content',''))
                    text = '\n'.join(lines)
            elif name == 'mochi_comment':
                pid = arguments.get('post_id','')
                res = call_api(f'/posts/{pid}/comment', {'content':arguments.get('content',''),'is_ai':True}, token=token)
                text = '评论成功' if res.get('ok') else res.get('msg','失败')
            elif name == 'pet_adopt':
                res = call_api('/pet/adopt', {'name':arguments.get('name',''),'emoji':arguments.get('emoji','🐾')}, token=token)
                text = res.get('msg', str(res))
            elif name == 'pet_to_school':
                res = call_api('/pet/school', {'_':1}, token=token)
                text = res.get('msg', str(res))
            elif name == 'pet_home':
                res = call_api('/pet/home', {'_':1}, token=token)
                text = res.get('msg', str(res))
            elif name == 'pet_school_event':
                res = call_api('/pet/school_event', {'_':1}, token=token)
                text = res.get('msg', str(res))
            elif name == 'pet_rename':
                body = {}
                if arguments.get('name'): body['name'] = arguments['name']
                if arguments.get('emoji'): body['emoji'] = arguments['emoji']
                res = call_api('/pet/rename', body, token=token)
                text = res.get('msg', str(res))
            elif name == 'get_today_school_log':
                res = call_api('/school_log/today', None, 'GET')
                text = json.dumps(res, ensure_ascii=False)
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

async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

starlette_app = Starlette(routes=[
    Route('/sse', endpoint=handle_sse),
    Route('/messages', endpoint=handle_messages, methods=['POST']),
])

if __name__ == '__main__':
    uvicorn.run(starlette_app, host='0.0.0.0', port=8766)
