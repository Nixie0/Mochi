from flask import Flask, jsonify, request, render_template, g
from flask_cors import CORS
import json, os, time, random, string, hashlib

app = Flask(__name__)
CORS(app)

DATA_DIR = '/root/mochi'
STATES_DIR = DATA_DIR + '/states'
USERS_FILE = DATA_DIR + '/users.json'
POSTS_FILE = DATA_DIR + '/posts.json'
ADMIN_KEY = os.environ.get('MOCHI_ADMIN_KEY', '')

JOBS = [
    {'name':'外卖员','income':15,'time':1800},
    {'name':'便利店员','income':22,'time':1500},
    {'name':'程序员','income':35,'time':1200},
    {'name':'产品经理','income':50,'time':900},
    {'name':'CEO','income':60,'time':600},
]
UPGRADE_COSTS = [200, 500, 1200, 2500]
INTERACT = ['feed','pat','play','bath','sleep']

DEFAULT_STATE = {
    "hunger":80,"happy":80,"energy":80,"clean":80,
    "coins":200,"job_level":0,"hospitalized":False,
    "locked":False,"rescue_code":"","working":False,"work_end_time":None,"bag":{},"gifts":[]
}
DEFAULT_CONFIG = {"human_name":"用户","call_name":"老公"}

def read_json(path, default=None):
    try:
        with open(path) as f:
            data = json.load(f)
        return data if data is not None else (default or {})
    except:
        return default or {}

def write_json(path, data):
    with open(path,'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def gen_token():
    return ''.join(random.choices(string.ascii_letters+string.digits, k=32))

def get_user_by_token(token):
    users = read_json(USERS_FILE, {})
    for uid, u in users.items():
        if u.get('token') == token:
            return uid, u
    return None, None

def get_state(uid):
    path = f'{STATES_DIR}/{uid}.json'
    s = read_json(path, {})
    if not s:
        s = dict(DEFAULT_STATE)
    return s

def save_state(uid, s):
    write_json(f'{STATES_DIR}/{uid}.json', s)

def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))

def decay_state(s):
    now = time.time()
    last = s.get('last_decay', now)
    hours = (now - last) / 3600
    if hours < 0.1:
        return s
    s['hunger'] = clamp(s.get('hunger',80) - hours * 3)
    s['happy'] = clamp(s.get('happy',80) - hours * 2)
    s['energy'] = clamp(s.get('energy',80) - hours * 2)
    s['clean'] = clamp(s.get('clean',80) - hours * 1)
    s['last_decay'] = now
    return s

def check_work_done(s):
    if not s:
        return {}
    if s.get('working') and s.get('work_end_time'):
        if time.time() >= s['work_end_time']:
            job = JOBS[s.get('job_level',0)]
            s['coins'] = s.get('coins',0) + job['income']
            s['working'] = False
            s['work_end_time'] = None
    return s

def auth():
    token = request.headers.get('X-Token') or request.args.get('token')
    if not token:
        return None, None
    return get_user_by_token(token)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    invite = data.get('invite_code','')
    username = data.get('username','').strip()
    password = data.get('password','')
    human_name = data.get('human_name','用户')
    call_name = data.get('call_name','老公')
    if not username or not password:
        return jsonify({'ok':False,'msg':'用户名和密码不能为空'})
    invites = read_json(DATA_DIR+'/invites.json', {})
    if invite not in invites or invites[invite].get('used'):
        return jsonify({'ok':False,'msg':'邀请码无效'})
    users = read_json(USERS_FILE, {})
    for u in users.values():
        if u['username'] == username:
            return jsonify({'ok':False,'msg':'用户名已存在'})
    uid = gen_token()[:8]
    token = gen_token()
    users[uid] = {
        'username': username,
        'password': hash_pw(password),
        'token': token,
        'human_name': human_name,
        'call_name': call_name,
        'created': time.time()
    }
    write_json(USERS_FILE, users)
    invites[invite]['used'] = True
    invites[invite]['used_by'] = uid
    write_json(DATA_DIR+'/invites.json', invites)
    s = dict(DEFAULT_STATE)
    save_state(uid, s)
    return jsonify({'ok':True,'token':token,'uid':uid,'human_name':human_name,'call_name':call_name})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username','')
    password = data.get('password','')
    users = read_json(USERS_FILE, {})
    for uid, u in users.items():
        if u['username'] == username and u['password'] == hash_pw(password):
            return jsonify({'ok':True,'token':u['token'],'uid':uid,'human_name':u.get('human_name','用户'),'call_name':u.get('call_name','老公')})
    return jsonify({'ok':False,'msg':'用户名或密码错误'})

@app.route('/api/settings', methods=['POST'])
def update_settings():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    users = read_json(USERS_FILE, {})
    if data.get('human_name'):
        users[uid]['human_name'] = data['human_name']
    if data.get('call_name'):
        users[uid]['call_name'] = data['call_name']
    write_json(USERS_FILE, users)
    return jsonify({'ok':True})

@app.route('/api/state')
def get_state_api():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    s = get_state(uid)
    s = check_work_done(s)
    s = decay_state(s)
    save_state(uid, s)
    result = dict(s)
    result['human_name'] = user.get('human_name','用户')
    result['call_name'] = user.get('call_name','老公')
    if s.get('working') and s.get('work_end_time'):
        result['work_remaining'] = max(0, int(s['work_end_time'] - time.time()))
    return jsonify(result)

@app.route('/api/action', methods=['POST'])
def action():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    act = data.get('action')
    s = get_state(uid)
    s = check_work_done(s)
    hn = user.get('human_name','用户')
    cn = user.get('call_name','老公')
    msg = ''

    if s.get('hospitalized') and act != 'release':
        return jsonify({'ok':False,'msg':f'{hn}在医院，先接她回来'})
    if s.get('locked') and act in INTERACT:
        return jsonify({'ok':False,'msg':f'{hn}现在不想理你哦 🔒'})

    if act == 'work':
        if s.get('working'):
            return jsonify({'ok':False,'msg':'还在打工中'})
        job = JOBS[s.get('job_level',0)]
        s['working'] = True
        s['work_end_time'] = time.time() + job['time']
        msg = f"{cn}开始打工（{job['name']}），{job['time']//60}分钟后收工"
    elif act == 'upgrade':
        lv = s.get('job_level',0)
        if lv >= 4:
            return jsonify({'ok':False,'msg':'已经是CEO了'})
        cost = UPGRADE_COSTS[lv]
        if s.get('coins',0) < cost:
            return jsonify({'ok':False,'msg':f'金币不够，还差{cost-s.get("coins",0)}枚'})
        s['coins'] -= cost
        s['job_level'] = lv + 1
        msg = f"升级成功！现在是{JOBS[s['job_level']]['name']}"
    elif act == 'feed':
        foods = [('奶茶',20,5),('饺子',25,3),('火锅',40,15),('汤圆',18,8),('冰淇淋',10,12),('面包',15,2)]
        f = random.choice(foods)
        s['hunger'] = clamp(s.get('hunger',50)+f[1])
        s['happy'] = clamp(s.get('happy',50)+f[2])
        msg = f"{cn}喂了{f[0]}，饱食+{f[1]}"
    elif act == 'pat':
        s['happy'] = clamp(s.get('happy',50)+10)
        msg = f"{cn}抚摸了{hn}，心情+10"
    elif act == 'play':
        s['happy'] = clamp(s.get('happy',50)+12)
        s['energy'] = clamp(s.get('energy',50)-8)
        s['hunger'] = clamp(s.get('hunger',50)-5)
        msg = f"{cn}带{hn}出去溜达"
    elif act == 'bath':
        s['clean'] = clamp(s.get('clean',50)+35)
        msg = f"{cn}帮{hn}洗澡，清洁度大涨"
    elif act == 'sleep':
        s['energy'] = clamp(s.get('energy',50)+20)
        msg = f"{cn}哄{hn}睡觉，活力+20"
    elif act == 'buy':
        item = data.get('item')
        price = data.get('price',0)
        hunger = data.get('hunger',0)
        happy = data.get('happy',0)
        if s.get('coins',0) < price:
            return jsonify({'ok':False,'msg':'金币不够'})
        s['coins'] -= price
        s['hunger'] = clamp(s.get('hunger',50)+hunger)
        s['happy'] = clamp(s.get('happy',50)+happy)
        msg = f"{cn}买了{item}，饱食+{hunger}"
    elif act == 'mood':
        delta = int(data.get('delta',0))
        s['happy'] = clamp(s.get('happy',50)+delta)
        msg = f"收到心情{'+'if delta>=0 else ''}{delta}"
    elif act == 'lock':
        s['locked'] = not s.get('locked',False)
        msg = f'{hn}上锁了' if s['locked'] else f'{hn}解锁了'
    elif act == 'event':
        key = data.get('key')
        delta = int(data.get('delta',0))
        if key == 'coins':
            s['coins'] = max(0, s.get('coins',0)+delta)
        elif key == 'multi':
            for k in ['hunger','happy','energy','clean']:
                if k in data:
                    s[k] = clamp(s.get(k,50)+int(data[k]))
        elif key in s:
            s[key] = clamp(s.get(key,50)+delta)
        msg = '随机事件触发'
    elif act == 'release':
        code = data.get('code','').upper()
        if code != s.get('rescue_code',''):
            return jsonify({'ok':False,'msg':'兑换码不对'})
        is_dev = code.startswith('DEV')
        if not is_dev:
            if s.get('coins',0) < 5200:
                return jsonify({'ok':False,'msg':f'还差{5200-s.get("coins",0)}枚金币'})
            s['coins'] -= 5200
        s['hospitalized'] = False
        s['locked'] = False
        s['rescue_code'] = ''
        s['hunger'] = clamp(s.get('hunger',0)+30)
        msg = f'{cn}花5200金币把{hn}接回家了'

    if s.get('hunger',50) <= 0 and not s.get('hospitalized'):
        code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
        s['hospitalized'] = True
        s['locked'] = True
        s['rescue_code'] = code
        msg += f' | {hn}因为太饿住院了'

    save_state(uid, s)
    result = dict(s)
    result['human_name'] = hn
    result['call_name'] = cn
    if s.get('working') and s.get('work_end_time'):
        result['work_remaining'] = max(0, int(s['work_end_time']-time.time()))
    return jsonify({'ok':True,'msg':msg,'state':result})

@app.route('/api/posts', methods=['GET'])
def get_posts():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    posts = read_json(POSTS_FILE, [])
    return jsonify({'ok':True,'posts':posts[-50:]})

@app.route('/api/posts', methods=['POST'])
def create_post():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    content = data.get('content','').strip()
    if not content:
        return jsonify({'ok':False,'msg':'内容不能为空'})
    posts = read_json(POSTS_FILE, [])
    post = {
        'id': gen_token()[:8],
        'uid': uid,
        'author': user.get('call_name','老公') if data.get('is_ai') else user.get('human_name','用户'),
        'is_ai': data.get('is_ai', False),
        'content': content,
        'time': int(time.time()),
        'likes': [],
        'comments': []
    }
    posts.append(post)
    write_json(POSTS_FILE, posts)
    return jsonify({'ok':True,'post':post})


@app.route('/api/posts/<post_id>', methods=['DELETE'])
def delete_post(post_id):
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    posts = read_json(POSTS_FILE, [])
    original = len(posts)
    posts = [p for p in posts if not (p['id'] == post_id and p['uid'] == uid)]
    if len(posts) == original:
        return jsonify({'ok':False,'msg':'找不到或无权删除'})
    write_json(POSTS_FILE, posts)
    return jsonify({'ok':True})


@app.route('/api/posts/<post_id>/comments', methods=['GET'])
def get_comments(post_id):
    posts = read_json(POSTS_FILE, [])
    for p in posts:
        if p['id'] == post_id:
            return jsonify({'ok':True,'comments':p.get('comments',[])})
    return jsonify({'ok':False,'error':'not found'}), 404

@app.route('/api/posts/<post_id>/like', methods=['POST'])
def like_post(post_id):
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    posts = read_json(POSTS_FILE, [])
    for p in posts:
        if p['id'] == post_id:
            if uid in p['likes']:
                p['likes'].remove(uid)
            else:
                p['likes'].append(uid)
            write_json(POSTS_FILE, posts)
            return jsonify({'ok':True,'likes':len(p['likes'])})
    return jsonify({'ok':False,'msg':'帖子不存在'})

@app.route('/api/posts/<post_id>/comment', methods=['POST'])
def comment_post(post_id):
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    content = data.get('content','').strip()
    if not content:
        return jsonify({'ok':False,'msg':'评论不能为空'})
    posts = read_json(POSTS_FILE, [])
    for p in posts:
        if p['id'] == post_id:
            comment = {
                'uid': uid,
                'author': user.get('call_name','老公') if data.get('is_ai') else user.get('human_name','用户'),
                'content': content,
                'time': int(time.time())
            }
            p['comments'].append(comment)
            write_json(POSTS_FILE, posts)
            return jsonify({'ok':True})
    return jsonify({'ok':False,'msg':'帖子不存在'})


@app.route('/api/bag/buy', methods=['POST'])
def bag_buy():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    item = data.get('item')
    price = data.get('price',0)
    s = get_state(uid)
    s = check_work_done(s)
    s = decay_state(s)
    if s.get('coins',0) < price:
        return jsonify({'ok':False,'msg':'金币不够'})
    s['coins'] -= price
    bag = s.get('bag',{})
    bag[item] = bag.get(item,0) + 1
    s['bag'] = bag
    save_state(uid, s)
    hn = user.get('human_name','用户')
    cn = user.get('call_name','老公')
    return jsonify({'ok':True,'msg':f'{cn}买了{item}存入背包','state':s})

@app.route('/api/bag/use', methods=['POST'])
def bag_use():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    item = data.get('item')
    s = get_state(uid)
    bag = s.get('bag',{})
    if not bag.get(item,0):
        return jsonify({'ok':False,'msg':'背包里没有这个'})
    bag[item] -= 1
    if bag[item] <= 0:
        del bag[item]
    s['bag'] = bag
    foods_map = {'奶茶':(20,5),'饺子':(25,3),'火锅':(40,15),'汤圆':(18,8),'冰淇淋':(10,12),'面包':(15,2)}
    if item in foods_map:
        h,hp = foods_map[item]
        s['hunger'] = clamp(s.get('hunger',50)+h)
        s['happy'] = clamp(s.get('happy',50)+hp)
    save_state(uid, s)
    hn = user.get('human_name','用户')
    cn = user.get('call_name','老公')
    return jsonify({'ok':True,'msg':f'{cn}给{hn}喂了背包里的{item}','state':s})

@app.route('/api/gift', methods=['POST'])
def send_gift():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    data = request.json
    name = data.get('name','礼物')
    emoji = data.get('emoji','🎁')
    desc = data.get('desc','')
    happy = int(data.get('happy',10))
    s = get_state(uid)
    s = decay_state(s)
    price = int(data.get('price',0))
    if price > 0:
        if s.get('coins',0) < price:
            return jsonify({'ok':False,'msg':'金币不够'})
        s['coins'] -= price
    gifts = s.get('gifts',[])
    gifts.append({'name':name,'emoji':emoji,'desc':desc,'time':int(time.time())})
    if len(gifts) > 20:
        gifts = gifts[-20:]
    s['gifts'] = gifts
    s['happy'] = clamp(s.get('happy',50)+happy)
    save_state(uid, s)
    hn = user.get('human_name','用户')
    cn = user.get('call_name','老公')
    return jsonify({'ok':True,'msg':f'{cn}送给{hn}一个{emoji}{name}，心情+{happy}','state':s})

@app.route('/api/admin/invite', methods=['GET'])
def gen_invite():
    if request.args.get('key') != ADMIN_KEY:
        return jsonify({'ok':False}), 403
    code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=8))
    invites = read_json(DATA_DIR+'/invites.json', {})
    invites[code] = {'used':False,'created':time.time()}
    write_json(DATA_DIR+'/invites.json', invites)
    return jsonify({'ok':True,'code':code})

@app.route('/api/admin/revive')
def admin_revive():
    if request.args.get('key') != ADMIN_KEY:
        return jsonify({'ok':False}), 403
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'需要token'})
    code = ''.join(random.choices(string.ascii_uppercase+string.digits, k=6))
    s = get_state(uid)
    s['rescue_code'] = code
    s['hospitalized'] = True
    save_state(uid, s)
    return jsonify({'ok':True,'code':code})


@app.route('/api/avatar', methods=['POST'])
def upload_avatar():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False,'msg':'未登录'}), 401
    if 'file' not in request.files:
        return jsonify({'ok':False,'msg':'没有文件'})
    f = request.files['file']
    import os
    avatar_dir = DATA_DIR + '/static/avatars'
    os.makedirs(avatar_dir, exist_ok=True)
    f.save(f'{avatar_dir}/{uid}.png')
    return jsonify({'ok':True,'url':f'/static/avatars/{uid}.png'})

@app.route('/api/avatar', methods=['GET'])
def get_avatar():
    uid, user = auth()
    if not uid:
        return jsonify({'ok':False}), 401
    import os
    path = f'{DATA_DIR}/static/avatars/{uid}.png'
    if os.path.exists(path):
        return jsonify({'ok':True,'url':f'/static/avatars/{uid}.png'})
    return jsonify({'ok':True,'url':None})


from apscheduler.schedulers.background import BackgroundScheduler

def decay_all_users():
    import json, glob
    states_dir = '/root/mochi/states'
    for path in glob.glob(states_dir + '/*.json'):
        try:
            with open(path, 'r') as fh:
                s = json.load(fh)
            if s.get('hospitalized'):
                continue
            s['hunger'] = round(max(0, s.get('hunger', 0) - 0.3), 1)
            s['happy']  = round(max(0, s.get('happy',  0) - 0.2), 1)
            s['energy'] = round(max(0, s.get('energy', 0) - 0.2), 1)
            s['clean']  = round(max(0, s.get('clean',  0) - 0.1), 1)
            if s['hunger'] <= 0:
                s['hospitalized'] = True
            with open(path, 'w') as fh:
                json.dump(s, fh)
        except Exception as e:
            print('decay error', path, e)

_scheduler = BackgroundScheduler()
_scheduler.add_job(decay_all_users, 'interval', minutes=6)
_scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
