import cv2
import mediapipe as mp
import pygame
import sys
import math
import random
import threading

# =====================
# INIT
# =====================

pygame.init()
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()

WIDTH, HEIGHT = 1280, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hand Survival Escape")
clock = pygame.time.Clock()

# =====================
# COLORS
# =====================

WHITE      = (255, 255, 255)
BLACK      = (0,   0,   0)
GREEN      = (0,   255, 0)
RED        = (255, 50,  50)
BLUE       = (0,   150, 255)
CYAN       = (0,   255, 255)
YELLOW     = (255, 255, 0)
ORANGE     = (255, 165, 0)
DARK_GREEN = (0,   100, 0)
PURPLE     = (150, 0,   150)
GRAY       = (80,  80,  80)
LIGHT_GRAY = (130, 130, 130)

# =====================
# CHARACTER SYSTEM
# =====================
# 8 characters — all drawn with pygame primitives (no emoji).
# Characters unlock permanently once the player scores high enough.
# best_score persists for the whole session.
#
# SHAPE KEY  (drawn centered at cx, cy with radius ~14):
#   0  Square       — always unlocked  (score >= 0)
#   1  Circle       — score >= 1000
#   2  Triangle     — score >= 2000
#   3  Diamond      — score >= 3000
#   4  Star         — score >= 4500
#   5  Pentagon     — score >= 6000
#   6  Cross/Plus   — score >= 7500
#   7  Crown        — score >= 9000  (elite)

CHARACTERS = [
    {'id': 0, 'name': 'Square',   'unlock': 0,    'color': CYAN,                 'glow': BLUE},
    {'id': 1, 'name': 'Circle',   'unlock': 1000, 'color': (100, 220, 255),      'glow': (0, 180, 255)},
    {'id': 2, 'name': 'Triangle', 'unlock': 2000, 'color': (120, 255, 120),      'glow': GREEN},
    {'id': 3, 'name': 'Diamond',  'unlock': 3000, 'color': (255, 80, 180),       'glow': PURPLE},
    {'id': 4, 'name': 'Star',     'unlock': 4500, 'color': YELLOW,               'glow': ORANGE},
    {'id': 5, 'name': 'Pentagon', 'unlock': 6000, 'color': (255, 140, 40),       'glow': RED},
    {'id': 6, 'name': 'Cross',    'unlock': 7500, 'color': (180, 100, 255),      'glow': (120, 0, 255)},
    {'id': 7, 'name': 'Crown',    'unlock': 9000, 'color': (255, 215, 0),        'glow': (255, 140, 0)},
]

best_score      = 0      # highest score ever achieved this session
p1_char_id      = 0      # selected character index for P1
p2_char_id      = 1      # selected character index for P2
char_select_for = 1      # which player is currently choosing (1 or 2)


def draw_character(surface, char_id, cx, cy, size, color=None, alpha_surf=False):
    """
    Draw character shape centered at (cx, cy).
    size = half-width (radius equivalent).
    color overrides the character's default if given.
    """
    ch  = CHARACTERS[char_id]
    col = color or ch['color']
    s   = size

    if char_id == 0:   # Square
        pygame.draw.rect(surface, col,
                         (cx - s, cy - s, s * 2, s * 2), border_radius=3)
        pygame.draw.rect(surface, WHITE,
                         (cx - s, cy - s, s * 2, s * 2), 2, border_radius=3)

    elif char_id == 1:  # Circle
        pygame.draw.circle(surface, col, (cx, cy), s)
        pygame.draw.circle(surface, WHITE, (cx, cy), s, 2)

    elif char_id == 2:  # Triangle (pointing up)
        pts = [(cx, cy - s), (cx - s, cy + s), (cx + s, cy + s)]
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, WHITE, pts, 2)

    elif char_id == 3:  # Diamond
        pts = [(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)]
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, WHITE, pts, 2)

    elif char_id == 4:  # 5-pointed Star
        pts = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            r     = s if i % 2 == 0 else s * 0.45
            pts.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, WHITE, pts, 2)

    elif char_id == 5:  # Pentagon
        pts = []
        for i in range(5):
            angle = math.pi / 2 + i * 2 * math.pi / 5
            pts.append((cx + s * math.cos(angle), cy - s * math.sin(angle)))
        pygame.draw.polygon(surface, col, pts)
        pygame.draw.polygon(surface, WHITE, pts, 2)

    elif char_id == 6:  # Cross / Plus
        t = max(4, s // 3)
        pygame.draw.rect(surface, col, (cx - t, cy - s, t * 2, s * 2))
        pygame.draw.rect(surface, col, (cx - s, cy - t, s * 2, t * 2))
        pygame.draw.rect(surface, WHITE, (cx - t, cy - s, t * 2, s * 2), 2)
        pygame.draw.rect(surface, WHITE, (cx - s, cy - t, s * 2, t * 2), 2)

    elif char_id == 7:  # Crown
        # Base bar
        pygame.draw.rect(surface, col, (cx - s, cy + s // 3, s * 2, s * 2 // 3))
        # Three spikes
        spike_pts = [
            (cx - s, cy + s // 3),  (cx - s, cy - s // 2),
            (cx,     cy),           (cx + s, cy - s // 2),
            (cx + s, cy + s // 3),
        ]
        pygame.draw.polygon(surface, col, spike_pts)
        pygame.draw.polygon(surface, WHITE, spike_pts, 2)
        pygame.draw.rect(surface, WHITE,
                         (cx - s, cy + s // 3, s * 2, s * 2 // 3), 2)


def is_unlocked(char_id):
    return best_score >= CHARACTERS[char_id]['unlock']


# =====================
# GAME STATE
# =====================

game_state = 0      # 0=Menu  1=Playing  2=Final Win  3=Stage Clear  4=Char Select
area       = 1
max_area   = 3

# =====================
# PLAYERS
# =====================

player_size = 30
enemy_size  = 25
smoothing   = 0.15

p1_x = 50.0
p1_y = float(HEIGHT // 2 - 50)
p2_x = 50.0
p2_y = float(HEIGHT // 2 + 50)
p2_speed = 5

# =====================
# EXIT
# =====================

exit_rect = pygame.Rect(WIDTH - 80, HEIGHT // 2 - 60, 60, 120)

# =====================
# WALLS  —  Easy → Medium → Hard
# =====================
#
# Area 1 (EASY):
#   Two short walls with huge passable gaps (~420 px).
#   Only 5 slow enemies.  Player can find the exit without stress.
#
# Area 2 (MEDIUM):
#   Three taller walls, gaps narrow to ~250 px.
#   9 enemies, faster.  Requires a little planning.
#
# Area 3 (HARD):
#   Four walls forming a tight maze, ~200 px gaps.
#   14 enemies, fast.  Real challenge to reach the exit.

walls      = []   # live pygame.Rect list used for collision + drawing
wall_data  = []   # area-3 animation data: {rect, axis, speed, amp, phase}

def create_walls():
    """
    Build wall rects for the current area.
    Area 3 (HARD) walls are animated — each has oscillation metadata stored
    in wall_data so update_moving_walls() can reposition them every frame.
    """
    global walls, wall_data
    walls     = []
    wall_data = []

    if area == 1:
        walls = [
            pygame.Rect(500,   0, 30, 300),
            pygame.Rect(850, 400, 30, 320),
        ]

    elif area == 2:
        walls = [
            pygame.Rect(380,   0, 35, 450),
            pygame.Rect(700, 250, 35, 470),
            pygame.Rect(980,   0, 35, 450),
        ]

    elif area == 3:
        # Each wall entry: base_x, base_y, w, h, axis ('y' or 'x'), speed, amplitude
        # axis='y'  → wall slides up and down
        # axis='x'  → wall slides left and right
        # Walls alternate direction so gaps open/close out of sync — harder to time
        hard_defs = [
            (290,   0, 40, 460, 'y', 1.2, 110),   # wall 1 — moves up/down
            (570, 230, 40, 460, 'y', 1.5, 100),   # wall 2 — moves up/down (faster)
            (850,   0, 40, 460, 'x', 1.0,  60),   # wall 3 — slides left/right
            (1100, 230, 40, 460, 'y', 1.8,  90),  # wall 4 — moves up/down (fastest)
        ]
        for i, (bx, by, w, h, axis, spd, amp) in enumerate(hard_defs):
            r = pygame.Rect(bx, by, w, h)
            walls.append(r)
            wall_data.append({
                'rect':  r,
                'bx':    bx,    # base X position
                'by':    by,    # base Y position
                'axis':  axis,  # 'x' or 'y'
                'speed': spd,   # oscillation speed (radians per second)
                'amp':   amp,   # max pixels of travel from base
                'phase': i * math.pi / 2,  # offset so walls are out of sync
            })


def update_moving_walls():
    """
    Called every frame during area 3 gameplay.
    Uses a sine wave to smoothly oscillate each wall back and forth.
    The actual pygame.Rect inside walls[] is updated in-place so
    push_out_of_walls() always reads the current position.
    """
    if area != 3 or not wall_data:
        return
    t = pygame.time.get_ticks() / 1000.0   # seconds since pygame started
    for wd in wall_data:
        offset = int(wd['amp'] * math.sin(wd['speed'] * t + wd['phase']))
        if wd['axis'] == 'y':
            wd['rect'].y = wd['by'] + offset
            # Clamp so walls never leave the screen
            wd['rect'].y = max(-10, min(HEIGHT - wd['rect'].height + 10, wd['rect'].y))
        else:
            wd['rect'].x = wd['bx'] + offset
            wd['rect'].x = max(0, min(WIDTH - wd['rect'].width, wd['rect'].x))

# =====================
# WALL COLLISION HELPER
# =====================

def push_out_of_walls(x, y, size):
    """
    Push a square object (x, y, size) out of any wall it overlaps.
    Resolves on the axis with the smallest overlap so entities slide
    along walls instead of stopping dead.
    """
    rect = pygame.Rect(int(x), int(y), size, size)
    for wall in walls:
        if not rect.colliderect(wall):
            continue
        ol = rect.right  - wall.left   # overlap from left
        or_ = wall.right - rect.left   # overlap from right
        ou = rect.bottom - wall.top    # overlap from above
        od = wall.bottom - rect.top    # overlap from below

        if min(ol, or_) < min(ou, od):
            if ol < or_:
                x -= ol
            else:
                x += or_
        else:
            if ou < od:
                y -= ou
            else:
                y += od

        rect = pygame.Rect(int(x), int(y), size, size)
    return x, y

# =====================
# STAGE CONFIG TABLE
# =====================

STAGE_CONFIG = {
    1: {'enemy_count_1p': 5,  'enemy_count_2p': 8,
        'speed_min': 1.8, 'speed_max': 2.8, 'label': 'EASY',   'color': GREEN},
    2: {'enemy_count_1p': 9,  'enemy_count_2p': 14,
        'speed_min': 3.0, 'speed_max': 4.5, 'label': 'MEDIUM', 'color': YELLOW},
    3: {'enemy_count_1p': 14, 'enemy_count_2p': 20,
        'speed_min': 4.2, 'speed_max': 6.0, 'label': 'HARD',   'color': RED},
}

enemies = []

# =====================
# CAMERA — THREADED
# =====================

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cap.set(cv2.CAP_PROP_FPS, 30)
if not cap.isOpened():
    print("Camera not detected — hand tracking disabled.")

mp_hands    = mp.solutions.hands
hands_model = mp_hands.Hands(
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.4,
)
mp_draw = mp.solutions.drawing_utils

_lock               = threading.Lock()
_hand_x             = 0
_hand_y             = 0
_is_detected        = False
_moving             = False
_cam_surface        = None
_cam_thread_running = True

def _camera_thread():
    global _hand_x, _hand_y, _is_detected, _moving, _cam_surface
    while _cam_thread_running:
        ret, frame = cap.read()
        if not ret:
            continue
        frame               = cv2.flip(frame, 1)
        rgb                 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results             = hands_model.process(rgb)
        rgb.flags.writeable = True

        detected = False
        hx, hy, mv = 0, 0, False
        if results.multi_hand_landmarks:
            for hl in results.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
                lm       = hl.landmark[9]
                hx       = int(lm.x * WIDTH)
                hy       = int(lm.y * HEIGHT)
                mv       = hl.landmark[12].y < hl.landmark[9].y
                detected = True
                break

        preview     = cv2.resize(frame, (220, 160))
        preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        surf        = pygame.surfarray.make_surface(preview_rgb.swapaxes(0, 1))

        with _lock:
            _hand_x      = hx
            _hand_y      = hy
            _is_detected = detected
            _moving      = mv
            _cam_surface = surf

cam_thread = threading.Thread(target=_camera_thread, daemon=True)
cam_thread.start()

def get_camera_state():
    with _lock:
        return _hand_x, _hand_y, _is_detected, _moving, _cam_surface

# =====================
# PARTICLES
# =====================

particles = []

def create_particle(x, y, color=CYAN):
    return {
        'x': float(x), 'y': float(y),
        'vx': random.uniform(-2, 2),
        'vy': random.uniform(-2, 2),
        'life': random.randint(15, 30),
        'color': color,
    }

# =====================
# FONTS & BUTTONS
# =====================

font        = pygame.font.SysFont("arial", 60, bold=True)
button_font = pygame.font.SysFont("arial", 40, bold=True)
menu_font   = pygame.font.SysFont("arial", 80, bold=True)
inst_font   = pygame.font.SysFont("arial", 24)
hud_font    = pygame.font.SysFont("arial", 32, bold=True)

# =====================
# AUDIO
# =====================
# Place bg_music.wav, horanghae.wav, and lose_sound.wav in the same
# folder as this script.  Missing files are skipped gracefully.

def _load_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except Exception as e:
        print(f"[Audio] Could not load '{path}': {e}")
        return None

win_sound  = _load_sound("horanghae_sound.wav")
lose_sound = _load_sound("lose_sound.wav")
if win_sound:  win_sound.set_volume(1.0)   # max volume for win
if lose_sound: lose_sound.set_volume(0.9)

# Background music — loops indefinitely at lower volume
try:
    pygame.mixer.music.load("bg_music.wav")
    pygame.mixer.music.set_volume(0.4)
    pygame.mixer.music.play(-1)   # -1 = loop forever
    _bg_music_loaded = True
except Exception as e:
    print(f"[Audio] Could not load 'bg_music.wav': {e}")
    _bg_music_loaded = False

_lose_played       = False   # True once lose_sound has fired this game-over
_stage_clear_played = False  # True once horanghae fired for current area clear

btn_1p      = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 50,  300, 80)
btn_2p      = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 + 80,  300, 80)
button_rect = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 + 100, 200, 60)

# Stage-clear screen buttons (repositioned each draw, but defined here)
btn_next_stage = pygame.Rect(WIDTH // 2 - 220, HEIGHT // 2 + 120, 200, 60)
btn_to_menu    = pygame.Rect(WIDTH // 2 +  20, HEIGHT // 2 + 120, 200, 60)

# =====================
# HELPERS
# =====================

def spawn_enemies(count):
    cfg = STAGE_CONFIG[area]
    out = []
    for _ in range(count):
        ex    = random.randint(WIDTH // 2, WIDTH - 60)
        ey    = random.randint(50, HEIGHT - 60)
        speed = random.uniform(cfg['speed_min'], cfg['speed_max'])
        out.append({'x': float(ex), 'y': float(ey), 'speed': speed})
    return out

def reset_game(num_players):
    global p1_x, p1_y, p2_x, p2_y, enemies, win, game_over, particles
    p1_x, p1_y = 50.0, float(HEIGHT // 2 - 50)
    p2_x, p2_y = 50.0, float(HEIGHT // 2 + 50)
    cfg     = STAGE_CONFIG[area]
    count   = cfg['enemy_count_2p'] if num_players == 2 else cfg['enemy_count_1p']
    enemies = spawn_enemies(count)
    create_walls()
    win = game_over = False
    particles = []

    global timer_start, timer_paused, timer_elapsed
    timer_start   = pygame.time.get_ticks()
    timer_paused  = False
    timer_elapsed = 0.0

# =====================
# RUNTIME VARS
# =====================

game_over   = False
win         = False
num_players = 1
p1_rect     = pygame.Rect(int(p1_x), int(p1_y), player_size, player_size)
p2_rect     = pygame.Rect(int(p2_x), int(p2_y), player_size, player_size)

# =====================
# TIMER & SCORE
# =====================
# Total time is measured from first play until the exit is reached.
# Score = max(0, BASE_SCORE - seconds_taken * PENALTY_PER_SEC)
# The faster you finish, the higher your score.

BASE_SCORE      = 10000   # perfect score if completed instantly
PENALTY_PER_SEC = 50      # points lost per second spent

timer_start   = 0      # pygame.time.get_ticks() when play began
timer_paused  = False  # True once game ends
timer_elapsed = 0.0    # total seconds when run ended
area_times    = []     # [(area_num, seconds), ...] one entry per cleared area
final_score   = 0      # computed once on win

# =====================
# MAIN LOOP
# =====================

_char_select_click = None   # set to (mx,my) when user clicks in char-select

while True:

    # ── EVENTS ──────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            _cam_thread_running = False
            cap.release()
            pygame.quit()
            sys.exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                _cam_thread_running = False
                cap.release()
                pygame.quit()
                sys.exit()
            if event.key == pygame.K_r and game_state == 1:
                _lose_played        = False
                _stage_clear_played = False
                reset_game(num_players)
                if _bg_music_loaded:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.play(-1)

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            if game_state == 0:
                if btn_1p.collidepoint(mx, my):
                    num_players     = 1
                    char_select_for = 1
                    game_state      = 4
                elif btn_2p.collidepoint(mx, my):
                    num_players     = 2
                    char_select_for = 1
                    game_state      = 4
            elif game_state == 2:
                if button_rect.collidepoint(mx, my):
                    area       = 1
                    game_state = 0
            elif game_state == 4:
                # Char-select grid click handled via _char_select_click flag
                _char_select_click = (mx, my)
            elif game_state == 3:
                if btn_next_stage.collidepoint(mx, my):
                    area += 1
                    area_times_carry    = list(area_times)
                    _stage_clear_played = False
                    reset_game(num_players)
                    area_times = area_times_carry
                    if _bg_music_loaded:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.play(-1)
                    game_state = 1
                elif btn_to_menu.collidepoint(mx, my):
                    area       = 1
                    area_times = []
                    game_state = 0

    # ── CAMERA STATE ────────────────────────────────────
    hand_x, hand_y, is_hand_detected, moving, cam_surface = get_camera_state()

    # Hand-tap on win / stage-clear buttons
    if is_hand_detected and moving:
        if game_state == 2 and button_rect.collidepoint(hand_x, hand_y):
            area       = 1
            game_state = 0
        elif game_state == 3:
            if btn_next_stage.collidepoint(hand_x, hand_y):
                area += 1
                area_times_carry    = list(area_times)
                _stage_clear_played = False
                reset_game(num_players)
                area_times = area_times_carry
                if _bg_music_loaded:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.play(-1)
                game_state = 1
            elif btn_to_menu.collidepoint(hand_x, hand_y):
                area       = 1
                area_times = []
                game_state = 0

    # ── KEYBOARD P2 ─────────────────────────────────────
    keys      = pygame.key.get_pressed()
    p2_moving = False

    if game_state == 1 and num_players == 2 and not game_over and not win:
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            p2_y -= p2_speed;  p2_moving = True
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            p2_y += p2_speed;  p2_moving = True
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            p2_x -= p2_speed;  p2_moving = True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            p2_x += p2_speed;  p2_moving = True

        p2_x = max(0, min(WIDTH  - player_size, p2_x))
        p2_y = max(0, min(HEIGHT - player_size, p2_y))
        p2_x, _ = push_out_of_walls(p2_x, p2_y, player_size)
        _, p2_y = push_out_of_walls(p2_x, p2_y, player_size)

    # ── GAME LOGIC ───────────────────────────────────────
    if game_state == 1 and not game_over and not win:

        # Animate area-3 walls before any collision checks
        update_moving_walls()

        # P1 movement — wall-safe interpolation
        # We move X and Y independently, running push_out_of_walls after
        # each axis so a wall on one axis never blocks sliding on the other.
        if is_hand_detected and moving:
            # --- X axis ---
            new_x = p1_x + (hand_x - p1_x) * smoothing
            new_x = max(0, min(WIDTH - player_size, new_x))
            new_x, _ = push_out_of_walls(new_x, p1_y, player_size)

            # --- Y axis ---
            new_y = p1_y + (hand_y - p1_y) * smoothing
            new_y = max(0, min(HEIGHT - player_size, new_y))
            _, new_y = push_out_of_walls(p1_x, new_y, player_size)

            p1_x, p1_y = new_x, new_y

        # Final clamp + wall push in case player was already overlapping
        p1_x = max(0, min(WIDTH  - player_size, p1_x))
        p1_y = max(0, min(HEIGHT - player_size, p1_y))
        p1_x, p1_y = push_out_of_walls(p1_x, p1_y, player_size)

        if random.random() < 0.3:
            particles.append(create_particle(p1_x + player_size // 2,
                                             p1_y + player_size // 2))

        p1_rect = pygame.Rect(int(p1_x), int(p1_y), player_size, player_size)
        p2_rect = pygame.Rect(int(p2_x), int(p2_y), player_size, player_size)

        # Enemy AI
        targets    = [(p1_x + player_size // 2, p1_y + player_size // 2)]
        if num_players == 2:
            targets.append((p2_x + player_size // 2, p2_y + player_size // 2))
        any_moving = moving or (num_players == 2 and p2_moving)

        for enemy in enemies:
            closest = min(targets,
                          key=lambda t: math.hypot(t[0]-enemy['x'], t[1]-enemy['y']))
            angle = math.atan2(closest[1]-enemy['y'], closest[0]-enemy['x'])

            if any_moving:
                spd = enemy['speed'] * 2
                enemy['x'] += spd * math.cos(angle)
                enemy['y'] += spd * math.sin(angle)
            else:
                spd = enemy['speed'] * 1.5
                enemy['x'] -= spd * math.cos(angle)
                enemy['y'] -= spd * math.sin(angle)
                if random.random() < 0.1:
                    particles.append(create_particle(
                        enemy['x'] + enemy_size // 2,
                        enemy['y'] + enemy_size // 2, ORANGE))

            enemy['x'] = max(0, min(WIDTH  - enemy_size, enemy['x']))
            enemy['y'] = max(0, min(HEIGHT - enemy_size, enemy['y']))
            # Split-axis wall push so enemies slide along walls too
            enemy['x'], _ = push_out_of_walls(enemy['x'], enemy['y'], enemy_size)
            _, enemy['y'] = push_out_of_walls(enemy['x'], enemy['y'], enemy_size)

        # Collision with enemies
        hit = False
        for enemy in enemies:
            e_rect = pygame.Rect(int(enemy['x']), int(enemy['y']),
                                 enemy_size, enemy_size)
            if p1_rect.colliderect(e_rect):
                hit = True; break
            if num_players == 2 and p2_rect.colliderect(e_rect):
                hit = True; break

        if hit:
            game_over     = True
            timer_paused  = True
            timer_elapsed = (pygame.time.get_ticks() - timer_start) / 1000.0
            for _ in range(20):
                particles.append(create_particle(p1_x, p1_y, RED))
            if not _lose_played:
                if _bg_music_loaded: pygame.mixer.music.stop()
                if lose_sound: lose_sound.play()
                _lose_played = True

        # Win condition
        p1_won = p1_rect.colliderect(exit_rect)
        p2_won = True if num_players == 1 else p2_rect.colliderect(exit_rect)

        if p1_won and p2_won and not game_over:
            # Freeze time for this area
            elapsed_now = (pygame.time.get_ticks() - timer_start) / 1000.0
            area_times.append((area, elapsed_now))
            timer_paused  = True
            timer_elapsed = elapsed_now
            if area < max_area:
                # Show stage-clear screen; player chooses next or menu
                game_state = 3
                if not _stage_clear_played:
                    if _bg_music_loaded: pygame.mixer.music.stop()
                    if win_sound: win_sound.play()
                    _stage_clear_played = True
            else:
                # All areas done — final win screen
                total_secs  = sum(t for _, t in area_times)
                final_score = max(0, int(BASE_SCORE - total_secs * PENALTY_PER_SEC))
                if final_score > best_score:
                    best_score = final_score
                win        = True
                game_state = 2
                if not _stage_clear_played:
                    if _bg_music_loaded: pygame.mixer.music.stop()
                    if win_sound: win_sound.play()
                    _stage_clear_played = True

    # ── DRAWING ─────────────────────────────────────────
    screen.fill(BLACK)

    # ── CHARACTER SELECT ────────────────────────────
    if game_state == 4:
        screen.fill((10, 10, 30))

        # Title
        who = f'P{char_select_for}' if num_players == 2 else 'YOUR'
        cs_title = hud_font.render(f'CHOOSE {who} CHARACTER', True, CYAN)
        screen.blit(cs_title, (WIDTH//2 - cs_title.get_width()//2, 30))

        # Score & unlock hint
        sc_hint = inst_font.render(
            f'Best score: {best_score:,}   |   Higher score unlocks more characters',
            True, YELLOW)
        screen.blit(sc_hint, (WIDTH//2 - sc_hint.get_width()//2, 75))

        # Grid: 4 per row, 2 rows
        COLS, ROWS = 4, 2
        CELL = 160
        grid_w = COLS * CELL
        gx0 = WIDTH  // 2 - grid_w // 2
        gy0 = 130

        cur_id = p1_char_id if char_select_for == 1 else p2_char_id
        mouse_pos = pygame.mouse.get_pos()

        for idx, ch in enumerate(CHARACTERS):
            row  = idx // COLS
            col  = idx % COLS
            cx   = gx0 + col * CELL + CELL // 2
            cy   = gy0 + row * (CELL + 60) + CELL // 2
            cell = pygame.Rect(gx0 + col * CELL, gy0 + row * (CELL + 60), CELL, CELL)

            unlocked = is_unlocked(ch['id'])
            selected = (ch['id'] == cur_id)
            hovered  = cell.collidepoint(mouse_pos)

            # Cell background
            bg_col = (40, 40, 80) if unlocked else (20, 20, 40)
            if selected:  bg_col = (30, 60, 30)
            if hovered and unlocked and not selected: bg_col = (50, 50, 100)
            pygame.draw.rect(screen, bg_col, cell, border_radius=10)

            # Border — gold for selected, dim for locked
            border_col = (255, 215, 0) if selected else \
                         (80, 80, 80)  if not unlocked else (100, 100, 160)
            pygame.draw.rect(screen, border_col, cell, 2, border_radius=10)

            if unlocked:
                draw_character(screen, ch['id'], cx, cy - 12, 24, ch['color'])
            else:
                # Locked — draw a padlock shape
                pygame.draw.rect(screen, GRAY, (cx-10, cy-6, 20, 16), border_radius=3)
                pygame.draw.arc(screen, GRAY,
                                pygame.Rect(cx-8, cy-20, 16, 20), 0, math.pi, 3)

            # Name label
            name_col = WHITE if unlocked else (60, 60, 60)
            name_s = inst_font.render(ch['name'], True, name_col)
            screen.blit(name_s, (cx - name_s.get_width()//2, cy + 18))

            # Unlock score label
            if not unlocked:
                req_s = inst_font.render(f"{ch['unlock']:,}", True, (100, 100, 100))
                screen.blit(req_s, (cx - req_s.get_width()//2, cy + 40))
            elif selected:
                sel_s = inst_font.render('SELECTED', True, (100, 220, 100))
                screen.blit(sel_s, (cx - sel_s.get_width()//2, cy + 40))

            # Handle click
            if _char_select_click and cell.collidepoint(_char_select_click) and unlocked:
                if char_select_for == 1:
                    p1_char_id = ch['id']
                else:
                    p2_char_id = ch['id']

        _char_select_click = None   # consume click

        # Back button (bottom-left) and Confirm button (bottom-right)
        cy_btn = gy0 + 2 * (CELL + 60) + 10
        back_btn    = pygame.Rect(gx0,             cy_btn, 180, 55)
        confirm_btn = pygame.Rect(gx0 + grid_w - 180, cy_btn, 180, 55)

        back_hov    = back_btn.collidepoint(mouse_pos)
        confirm_hov = confirm_btn.collidepoint(mouse_pos)

        pygame.draw.rect(screen, (120,0,0) if back_hov else (60,0,0),
                         back_btn, border_radius=8)
        pygame.draw.rect(screen, WHITE, back_btn, 2, border_radius=8)
        bt = button_font.render('BACK', True, WHITE)
        screen.blit(bt, (back_btn.centerx - bt.get_width()//2,
                         back_btn.centery - bt.get_height()//2))

        confirm_label = 'CONFIRM' if (num_players == 1 or char_select_for == 2) \
                         else f'NEXT: P2'
        pygame.draw.rect(screen, (0,120,0) if confirm_hov else (0,60,0),
                         confirm_btn, border_radius=8)
        pygame.draw.rect(screen, WHITE, confirm_btn, 2, border_radius=8)
        ct = button_font.render(confirm_label, True, WHITE)
        screen.blit(ct, (confirm_btn.centerx - ct.get_width()//2,
                         confirm_btn.centery - ct.get_height()//2))

        # Handle back / confirm clicks
        if event.type == pygame.MOUSEBUTTONDOWN if False else False: pass  # handled below
        for _ev in pygame.event.get(pygame.MOUSEBUTTONDOWN):
            _mx, _my = _ev.pos
            if back_btn.collidepoint(_mx, _my):
                game_state = 0
            elif confirm_btn.collidepoint(_mx, _my):
                if num_players == 2 and char_select_for == 1:
                    char_select_for = 2
                else:
                    # Start the game
                    area = 1; area_times = []
                    _lose_played = False; _stage_clear_played = False
                    reset_game(num_players)
                    if _bg_music_loaded:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.play(-1)
                    game_state = 1

    # MENU
    elif game_state == 0:
        title = menu_font.render("HAND SURVIVAL ESCAPE", True, CYAN)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//4))

        pygame.draw.rect(screen, BLUE,   btn_1p)
        pygame.draw.rect(screen, WHITE,  btn_1p, 3)
        pygame.draw.rect(screen, PURPLE, btn_2p)
        pygame.draw.rect(screen, WHITE,  btn_2p, 3)

        t1 = button_font.render("1 PLAYER",  True, WHITE)
        t2 = button_font.render("2 PLAYERS", True, WHITE)
        screen.blit(t1, (btn_1p.centerx - t1.get_width()//2,
                         btn_1p.centery - t1.get_height()//2))
        screen.blit(t2, (btn_2p.centerx - t2.get_width()//2,
                         btn_2p.centery - t2.get_height()//2))

        i1 = inst_font.render("Player 1: Use Hand Tracking (Open Hand to Move)", True, WHITE)
        i2 = inst_font.render("Player 2: Use WASD or Arrow Keys",                 True, WHITE)
        screen.blit(i1, (WIDTH//2 - i1.get_width()//2, HEIGHT//2 + 200))
        screen.blit(i2, (WIDTH//2 - i2.get_width()//2, HEIGHT//2 + 230))

    elif game_state == 3:
        # ── STAGE CLEAR SCREEN ───────────────────────────
        ov = pygame.Surface((WIDTH, HEIGHT))
        ov.set_alpha(200)
        ov.fill(BLACK)
        screen.blit(ov, (0, 0))

        cy = 100

        # Stage cleared title
        cfg_done  = STAGE_CONFIG[area]
        done_txt  = font.render(f"AREA {area}  CLEARED!", True, cfg_done['color'])
        screen.blit(done_txt, (WIDTH//2 - done_txt.get_width()//2, cy));  cy += 80

        # Time for this area
        last_secs = area_times[-1][1]
        lm  = int(last_secs) // 60
        ls  = int(last_secs) % 60
        lms = int((last_secs % 1) * 100)
        time_row = hud_font.render(
            f"Time this stage:  {lm:02d}:{ls:02d}.{lms:02d}", True, CYAN)
        screen.blit(time_row, (WIDTH//2 - time_row.get_width()//2, cy));  cy += 40

        # Cumulative time so far
        cum_secs = sum(t for _, t in area_times)
        cm  = int(cum_secs) // 60
        cs  = int(cum_secs) % 60
        cms = int((cum_secs % 1) * 100)
        cum_row = inst_font.render(
            f"Total time so far:  {cm:02d}:{cs:02d}.{cms:02d}", True, WHITE)
        screen.blit(cum_row, (WIDTH//2 - cum_row.get_width()//2, cy));  cy += 35

        # Running score preview
        running_score = max(0, int(BASE_SCORE - cum_secs * PENALTY_PER_SEC))
        sc_col  = GREEN if running_score > 7000 else YELLOW if running_score > 4000 else ORANGE
        sc_row  = hud_font.render(f"Score so far:  {running_score:,}", True, sc_col)
        screen.blit(sc_row, (WIDTH//2 - sc_row.get_width()//2, cy));  cy += 60

        # Next stage label
        next_area   = area + 1
        cfg_next    = STAGE_CONFIG[next_area]
        next_label  = cfg_next['label']          # e.g. 'MEDIUM' or 'HARD'

        # ── Buttons ──
        BW, BH = 220, 65
        gap    = 30
        total_w = BW * 2 + gap
        bx_left  = WIDTH // 2 - total_w // 2
        bx_right = bx_left + BW + gap

        btn_next_stage.update(bx_left,  cy, BW, BH)
        btn_to_menu.update   (bx_right, cy, BW, BH)

        mouse_pos = pygame.mouse.get_pos()

        # Next stage button
        next_hover = btn_next_stage.collidepoint(mouse_pos) or \
                     (is_hand_detected and btn_next_stage.collidepoint(hand_x, hand_y))
        pygame.draw.rect(screen,
                         cfg_next['color'] if next_hover else (0, 80, 0),
                         btn_next_stage, border_radius=8)
        pygame.draw.rect(screen, WHITE, btn_next_stage, 2, border_radius=8)
        n_txt = button_font.render(next_label, True, WHITE)
        screen.blit(n_txt, (btn_next_stage.centerx - n_txt.get_width()//2,
                            btn_next_stage.centery - n_txt.get_height()//2))

        # Menu button
        menu_hover = btn_to_menu.collidepoint(mouse_pos) or \
                     (is_hand_detected and btn_to_menu.collidepoint(hand_x, hand_y))
        pygame.draw.rect(screen,
                         BLUE if menu_hover else (0, 40, 100),
                         btn_to_menu, border_radius=8)
        pygame.draw.rect(screen, WHITE, btn_to_menu, 2, border_radius=8)
        m_txt = button_font.render("MENU", True, WHITE)
        screen.blit(m_txt, (btn_to_menu.centerx - m_txt.get_width()//2,
                            btn_to_menu.centery - m_txt.get_height()//2))

        # Camera preview still visible on stage-clear
        if cam_surface:
            screen.blit(cam_surface, (WIDTH - 240, HEIGHT - 180))

    elif game_state == 1 or game_state == 2:

        # Particles
        alive = []
        for p in particles:
            p['x'] += p['vx']; p['y'] += p['vy']; p['life'] -= 1
            if p['life'] > 0:
                pygame.draw.circle(screen, p['color'],
                                   (int(p['x']), int(p['y'])), 3)
                alive.append(p)
        particles = alive

        # Exit
        pygame.draw.rect(screen, DARK_GREEN, exit_rect)
        pygame.draw.rect(screen, GREEN,      exit_rect, 3)
        ex_lbl = inst_font.render("EXIT", True, GREEN)
        screen.blit(ex_lbl, (exit_rect.centerx - ex_lbl.get_width()//2,
                              exit_rect.centery - ex_lbl.get_height()//2))

        # Walls — red tint in HARD mode to signal they move
        wall_fill   = (100, 30, 30) if area == 3 else GRAY
        wall_border = (220, 80, 80) if area == 3 else LIGHT_GRAY
        for w in walls:
            pygame.draw.rect(screen, wall_fill,   w)
            pygame.draw.rect(screen, wall_border, w, 2)

        # Player 1 — selected character shape
        p1cx = int(p1_x) + player_size // 2
        p1cy = int(p1_y) + player_size // 2
        p1col = CHARACTERS[p1_char_id]['color'] if moving else \
                tuple(max(0, c - 80) for c in CHARACTERS[p1_char_id]['color'])
        draw_character(screen, p1_char_id, p1cx, p1cy, player_size // 2, p1col)

        # Player 2 — selected character shape
        if num_players == 2:
            p2cx = int(p2_x) + player_size // 2
            p2cy = int(p2_y) + player_size // 2
            p2col = CHARACTERS[p2_char_id]['color'] if p2_moving else \
                    tuple(max(0, c - 80) for c in CHARACTERS[p2_char_id]['color'])
            draw_character(screen, p2_char_id, p2cx, p2cy, player_size // 2, p2col)

        # Enemies
        tick       = pygame.time.get_ticks()
        pulse      = int(math.sin(tick * 0.002) * 2)
        any_moving = moving or (num_players == 2 and p2_moving)

        for enemy in enemies:
            ds          = enemy_size + pulse
            enemy_color = RED   if any_moving else ORANGE
            eye_color   = BLACK if any_moving else WHITE
            pygame.draw.rect(screen, enemy_color,
                             (int(enemy['x']), int(enemy['y']), ds, ds))
            pygame.draw.circle(screen, eye_color,
                               (int(enemy['x']) + ds//2,
                                int(enemy['y']) + ds//2), 4)

        # Hand cursor
        if is_hand_detected:
            col = GREEN if moving else (150, 150, 150)
            pygame.draw.circle(screen, col, (hand_x, hand_y), 20, 3)
            pygame.draw.circle(screen, col, (hand_x, hand_y), 5)
            if moving:
                pygame.draw.line(screen, (50, 50, 50),
                                 (hand_x, hand_y),
                                 (int(p1_x) + player_size//2,
                                  int(p1_y) + player_size//2), 2)

        # HUD
        if game_state == 1:
            cfg      = STAGE_CONFIG[area]
            area_lbl = hud_font.render(
                f"AREA {area}  —  {cfg['label']}", True, cfg['color'])
            screen.blit(area_lbl,
                        (WIDTH//2 - area_lbl.get_width()//2, 10))

            inst_txt = "RUN! ENEMIES ARE CHASING!" if any_moving \
                       else "STOP! ENEMIES ARE RETREATING!"
            inst_col = RED if any_moving else GREEN
            screen.blit(inst_font.render(inst_txt, True, inst_col), (20, 50))

            screen.blit(inst_font.render("P1: Hand", True, CYAN), (20, 80))
            if num_players == 2:
                screen.blit(inst_font.render("P2: Keyboard", True, PURPLE), (20, 110))

            # ── Live timer + live score (top-right) ──
            live_secs = (pygame.time.get_ticks() - timer_start) / 1000.0 \
                        if not timer_paused else timer_elapsed
            live_score = max(0, int(BASE_SCORE - live_secs * PENALTY_PER_SEC))

            mins = int(live_secs) // 60
            secs = int(live_secs) % 60
            ms   = int((live_secs % 1) * 100)
            time_str = f"{mins:02d}:{secs:02d}.{ms:02d}"

            # Colour shifts green → yellow → red as score drops
            if live_score > 7000:
                hud_col = GREEN
            elif live_score > 4000:
                hud_col = YELLOW
            else:
                hud_col = RED

            t_surf  = hud_font.render(f"TIME   {time_str}",       True, hud_col)
            sc_surf = hud_font.render(f"SCORE  {live_score:,}",   True, hud_col)
            screen.blit(t_surf,  (WIDTH - t_surf.get_width()  - 14, 10))
            screen.blit(sc_surf, (WIDTH - sc_surf.get_width() - 14, 46))

            if game_over:
                go_txt = font.render("GAME OVER — Press R to Restart", True, RED)
                screen.blit(go_txt, (WIDTH//2 - go_txt.get_width()//2, HEIGHT//2 - 50))
                # Time and score reached before dying
                ge_mins = int(timer_elapsed) // 60
                ge_secs = int(timer_elapsed) % 60
                ge_ms   = int((timer_elapsed % 1) * 100)
                dead_score = max(0, int(BASE_SCORE - timer_elapsed * PENALTY_PER_SEC))
                ge_t1 = inst_font.render(
                    f"Time: {ge_mins:02d}:{ge_secs:02d}.{ge_ms:02d}", True, ORANGE)
                ge_t2 = inst_font.render(
                    f"Score reached: {dead_score:,}  (finish faster for a higher score!)",
                    True, YELLOW)
                screen.blit(ge_t1, (WIDTH//2 - ge_t1.get_width()//2, HEIGHT//2 + 10))
                screen.blit(ge_t2, (WIDTH//2 - ge_t2.get_width()//2, HEIGHT//2 + 44))

        # ── WIN OVERLAY ──────────────────────────────
        if game_state == 2 or win:
            ov = pygame.Surface((WIDTH, HEIGHT))
            ov.set_alpha(160)
            ov.fill(BLACK)
            screen.blit(ov, (0, 0))

            cy = 100   # cursor y — stack rows from here

            # Title
            label = "YOU ESCAPED!" if num_players == 1 else "BOTH ESCAPED!"
            txt   = font.render(label, True, YELLOW)
            screen.blit(txt, (WIDTH//2 - txt.get_width()//2, cy));  cy += 80

            # Per-area time rows
            for a_num, a_secs in area_times:
                cfg_a = STAGE_CONFIG[a_num]
                am    = int(a_secs) // 60
                as_   = int(a_secs) % 60
                ams   = int((a_secs % 1) * 100)
                row   = inst_font.render(
                    f"Area {a_num}  ({cfg_a['label']})     {am:02d}:{as_:02d}.{ams:02d}",
                    True, cfg_a['color'])
                screen.blit(row, (WIDTH//2 - row.get_width()//2, cy));  cy += 30

            cy += 10

            # Total time
            total = sum(t for _, t in area_times)
            tm, ts_ = int(total) // 60, int(total) % 60
            tms     = int((total % 1) * 100)
            tot_row = hud_font.render(
                f"TOTAL TIME     {tm:02d}:{ts_:02d}.{tms:02d}", True, CYAN)
            screen.blit(tot_row, (WIDTH//2 - tot_row.get_width()//2, cy));  cy += 50

            # Final score — big and prominent
            sc_row = font.render(f"SCORE   {final_score:,}", True,
                                 GREEN if final_score > 7000 else
                                 YELLOW if final_score > 4000 else ORANGE)
            screen.blit(sc_row, (WIDTH//2 - sc_row.get_width()//2, cy));  cy += 70

            # Score hint
            hint = inst_font.render(
                "Faster escape = higher score  |  Max: 10,000", True, (160, 160, 160))
            screen.blit(hint, (WIDTH//2 - hint.get_width()//2, cy));  cy += 50

            # BACK button
            btn_hover = button_rect.collidepoint(pygame.mouse.get_pos())
            if is_hand_detected and button_rect.collidepoint(hand_x, hand_y):
                btn_hover = True
            br = pygame.Rect(WIDTH//2 - 100, cy, 200, 55)
            pygame.draw.rect(screen, GREEN if btn_hover else DARK_GREEN, br)
            pygame.draw.rect(screen, WHITE, br, 3)
            btn_txt = button_font.render("BACK", True, WHITE)
            screen.blit(btn_txt, (br.centerx - btn_txt.get_width()//2,
                                  br.centery - btn_txt.get_height()//2))
            # update button_rect so hand-hover still works
            button_rect = br

    # Camera preview
    if cam_surface:
        screen.blit(cam_surface, (WIDTH - 240, HEIGHT - 180))

    pygame.display.update()
    clock.tick(60)