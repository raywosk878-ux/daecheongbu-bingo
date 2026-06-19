from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'daecheongbu-bingo-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ── 질문 데이터 ──────────────────────────────────────────────
QUESTIONS = {
    1:  {"type": "quiz",    "text": "우리 교회 담임목사님 이름은?",         "answer": "김주선"},
    2:  {"type": "quiz",    "text": "대청부 담당목사님은?",                  "answer": "장두영"},
    3:  {"type": "quiz",    "text": "대청부 총무는?",                        "answer": "김동민"},
    4:  {"type": "quiz",    "text": "대청부 수련회가 언제인가?",             "answer": "8월 6일~8일"},
    5:  {"type": "choice",  "text": "계획형 vs 즉흥형?",                    "options": ["계획형", "즉흥형"]},
    6:  {"type": "choice",  "text": "아침형 vs 밤형?",                      "options": ["아침형", "밤형"]},
    7:  {"type": "choice",  "text": "현실적 vs 낭만적?",                    "options": ["현실적", "낭만적"]},
    8:  {"type": "choice",  "text": "새로운 것 vs 익숙한 것?",              "options": ["새로운 것", "익숙한 것"]},
    9:  {"type": "open",    "text": "좋아하는 찬양이나 노래는?"},
    10: {"type": "open",    "text": "취미나 관심사는?"},
    11: {"type": "open",    "text": "좋아하는 성경 말씀이나 신앙 경험은?"},
    12: {"type": "open",    "text": "요즘 좋아하는 음식은?"},
    13: {"type": "open",    "text": "나의 고향은?"},
    14: {"type": "open",    "text": "가장 좋아하는 계절이나 날씨는?"},
    15: {"type": "deep",    "text": "당신을 설명하는 단어 3개는?"},
    16: {"type": "vs",      "text": "짜장 vs 짬뽕?",                        "options": ["짜장", "짬뽕"]},
    17: {"type": "vs",      "text": "펩시 vs 코카콜라?",                    "options": ["펩시", "코카콜라"]},
    18: {"type": "vs",      "text": "겨울 vs 여름?",                        "options": ["겨울", "여름"]},
    19: {"type": "vs",      "text": "초콜릿 vs 젤리?",                      "options": ["초콜릿", "젤리"]},
    20: {"type": "vs",      "text": "이재훈 vs 이제훈?",                    "options": ["이재훈", "이제훈"]},
    21: {"type": "vs",      "text": "디자인은 싫은데 너무 비싸고 정성 가득 담긴 선물 vs 취향은 완벽하게 저격했는데 길가다 주운 것 같은 성의 없는 선물?", "options": ["비싼 정성 선물", "취향 저격 선물"]},
    22: {"type": "vs",      "text": "스쿼트 하다가 바지 터져서 헬스장 사람들과 눈 마주치기 vs 런닝머신 뛰다가 화려하게 넘어져서 유튜브 쇼츠에 박제되기?", "options": ["바지 터짐", "유튜브 박제"]},
    23: {"type": "vs",      "text": "뜨아 vs 아아?",                        "options": ["뜨아", "아아"]},
    24: {"type": "vs",      "text": "회의시간에 나도 모르게 '아멘!' 외치기 vs 기도 끝난 후 '건배!' 외치기?", "options": ["회의중 아멘!", "식사중 건배!"]},
    25: {"type": "vs",      "text": "연세대 vs 고려대?",                    "options": ["연세대", "고려대"]},
}

TYPE_LABELS = {
    "quiz":   "📝 퀴즈",
    "choice": "🙋 나는 어떤 사람?",
    "open":   "💬 자유 답변",
    "deep":   "🌊 깊은 질문",
    "vs":     "⚡ 양자택일",
}

# ── 게임 상태 ─────────────────────────────────────────────────
game_state = {
    "players": {},        # sid -> {name, board, cleared, bingo}
    "cleared": set(),     # 운영자가 지운 번호들
    "current_q": None,    # 현재 진행 중인 번호
    "answers": [],        # [{name, text}]
    "vs_votes": {},       # option -> count
}

def make_board():
    nums = list(range(1, 26))
    random.shuffle(nums)
    return nums  # 5×5 순서, index 12 = FREE

@app.route('/')
def index():
    return render_template('player.html')

@app.route('/operator')
def operator():
    return render_template('operator.html', questions=QUESTIONS, type_labels=TYPE_LABELS)

# ── 소켓 이벤트 ───────────────────────────────────────────────
@socketio.on('connect')
def on_connect():
    pass

@socketio.on('join')
def on_join(data):
    name = data.get('name', '익명').strip() or '익명'
    board = make_board()
    game_state['players'][request.sid] = {
        'name': name,
        'board': board,
        'cleared': list(game_state['cleared']),
        'bingo': False,
    }
    emit('init', {
        'board': board,
        'cleared': list(game_state['cleared']),
        'current_q': game_state['current_q'],
        'question': QUESTIONS.get(game_state['current_q']) if game_state['current_q'] else None,
    })
    emit('player_list', _player_list(), broadcast=True)
    emit('scoreboard', _scoreboard(), broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    game_state['players'].pop(request.sid, None)
    emit('player_list', _player_list(), broadcast=True)
    emit('scoreboard', _scoreboard(), broadcast=True)

@socketio.on('open_question')
def on_open_question(data):
    num = int(data['num'])
    if num in game_state['cleared']:
        return
    game_state['current_q'] = num
    game_state['answers'] = []
    game_state['vs_votes'] = {}
    q = QUESTIONS[num]
    emit('question_opened', {
        'num': num,
        'question': q,
        'type_label': TYPE_LABELS[q['type']],
    }, broadcast=True)

@socketio.on('send_answer')
def on_answer(data):
    sid = request.sid
    player = game_state['players'].get(sid)
    if not player:
        return
    answer = {
        'name': player['name'],
        'text': data.get('text', '').strip(),
    }
    game_state['answers'].append(answer)
    emit('new_answer', answer, broadcast=True)

@socketio.on('vote_vs')
def on_vote_vs(data):
    sid = request.sid
    player = game_state['players'].get(sid)
    if not player:
        return
    option = data.get('option', '')
    game_state['vs_votes'][sid] = option
    # 집계
    counts = {}
    for v in game_state['vs_votes'].values():
        counts[v] = counts.get(v, 0) + 1
    emit('vs_result', {'votes': counts, 'voter': player['name'], 'choice': option}, broadcast=True)

@socketio.on('clear_number')
def on_clear_number(data):
    num = int(data['num'])
    game_state['cleared'].add(num)
    game_state['current_q'] = None
    # 각 참여자 cleared 업데이트
    for sid, p in game_state['players'].items():
        if num not in p['cleared']:
            p['cleared'].append(num)
            bingo = check_bingo(p['board'], p['cleared'])
            if bingo and not p['bingo']:
                p['bingo'] = True
                socketio.emit('bingo_alert', {'name': p['name']}, broadcast=True)
    emit('number_cleared', {'num': num}, broadcast=True)
    emit('scoreboard', _scoreboard(), broadcast=True)

@socketio.on('reset_game')
def on_reset():
    game_state['players'] = {}
    game_state['cleared'] = set()
    game_state['current_q'] = None
    game_state['answers'] = []
    game_state['vs_votes'] = {}
    emit('game_reset', broadcast=True)

# ── 헬퍼 ─────────────────────────────────────────────────────
def _player_list():
    return [{'name': p['name']} for p in game_state['players'].values()]

def _scoreboard():
    scores = []
    for p in game_state['players'].values():
        scores.append({'name': p['name'], 'count': len(p['cleared'])})
    return sorted(scores, key=lambda x: x['count'])

def check_bingo(board, cleared):
    grid = [[board[r*5+c] in cleared for c in range(5)] for r in range(5)]
    grid[2][2] = True  # FREE
    for i in range(5):
        if all(grid[i]):    return True
        if all(grid[r][i] for r in range(5)): return True
    if all(grid[i][i] for i in range(5)):   return True
    if all(grid[i][4-i] for i in range(5)): return True
    return False

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
