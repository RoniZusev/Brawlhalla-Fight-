import pygame
import socket
import pickle
from threading import Thread
import sys

def run_game(player_id):
    pygame.init()

    screen_width, screen_height = 960, 540
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption(f"Game Screen - {player_id.upper()}")

    font = pygame.font.SysFont('Arial', 18)

    background = pygame.image.load("game_background.jpg")
    background = pygame.transform.scale(background, (screen_width, screen_height))

    image_paths = {
        "blue": ("blue_player(standing).png", (70, 160), "blue_attacking.png", (200, 150)),
        "red": ("Red_player-removebg-preview.png", (110, 150), "red_attacking.png", (200, 150))
    }

    player_image = pygame.image.load(image_paths[player_id][0])
    player_image = pygame.transform.scale(player_image, image_paths[player_id][1])

    player_attack_image = pygame.image.load(image_paths[player_id][2])
    player_attack_image = pygame.transform.scale(player_attack_image, image_paths[player_id][3])

    opponent_id = "red" if player_id == "blue" else "blue"
    opponent_image = pygame.image.load(image_paths[opponent_id][0])
    opponent_image = pygame.transform.scale(opponent_image, image_paths[opponent_id][1])

    player_width, player_height = image_paths[player_id][1]
    opponent_width, opponent_height = image_paths[opponent_id][1]

    ground_height = 50
    ground_color = (159, 164, 73)

    player_x, player_y = (80 if player_id == "blue" else 680), screen_height - ground_height - player_height
    player_speed = 0.8
    velocity_y = 0
    jump_power = -9
    gravity = 0.3
    on_ground = True

    opponent_x, opponent_y = (680 if player_id == "blue" else 80), screen_height - ground_height - opponent_height

    server_address = ('localhost', 1729)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(0.01)
    client_socket.sendto(f"PLAYER_ID:{player_id}".encode(), server_address)

    platforms = [
        pygame.Rect(350, 150, 150, 15),
        pygame.Rect(600, 280, 150, 15),
        pygame.Rect(100, 220, 150, 15)
    ]
    platform_color = (0, 0, 0)

    running = True
    frame_count = 0

    is_attacking = False
    attack_timer = 0
    attack_duration = 10

    max_health = 100
    player_health = max_health
    opponent_health = max_health

    waiting_for_other = True

    def receive_positions():
        nonlocal opponent_x, opponent_y, opponent_health, player_health, is_attacking, attack_timer, waiting_for_other
        while True:
            try:
                message, _ = client_socket.recvfrom(8192)
                if message.startswith(b"POSITIONS:"):
                    positions = pickle.loads(message.split(b":", 1)[1])
                    if opponent_id in positions and positions[opponent_id].get("x") is not None:
                        opponent_x = positions[opponent_id].get("x", opponent_x)
                        opponent_y = positions[opponent_id].get("y", opponent_y)
                        opponent_health = positions[opponent_id].get("health", opponent_health)
                        waiting_for_other = False
                    if player_id in positions:
                        player_health = positions[player_id].get("health", player_health)
                elif message.startswith(f"IsAttacking:{player_id}".encode()):
                    is_attacking = True
                    attack_timer = attack_duration
            except socket.timeout:
                continue
            except Exception as e:
                print("Error receiving:", e)

    Thread(target=receive_positions, daemon=True).start()

    while running:
        screen.blit(background, (0, 0))
        pygame.draw.rect(screen, ground_color, (0, screen_height - ground_height, screen_width, ground_height))

        # Opponent health bar
        pygame.draw.rect(screen, (255, 0, 0), (20, 20, 200, 20))
        pygame.draw.rect(screen, (0, 255, 0), (20, 20, 200 * opponent_health // max_health, 20))
        screen.blit(font.render(opponent_id.upper(), True, (255, 255, 255)), (230, 22))

        # Player health bar
        pygame.draw.rect(screen, (255, 0, 0), (screen_width - 220, 20, 200, 20))
        pygame.draw.rect(screen, (0, 255, 0), (screen_width - 220, 20, 200 * player_health // max_health, 20))
        screen.blit(font.render(player_id.upper(), True, (255, 255, 255)), (screen_width - 270, 22))

        keys = pygame.key.get_pressed()
        if keys[pygame.K_a] and player_x > 0:
            player_x -= player_speed
            is_attacking = False
        if keys[pygame.K_d] and player_x < screen_width - player_width:
            player_x += player_speed
            is_attacking = False
        if keys[pygame.K_w] and on_ground:
            velocity_y = jump_power
            on_ground = False
            is_attacking = False
        if keys[pygame.K_SPACE] and not is_attacking:
            is_attacking = True
            attack_timer = attack_duration
            client_socket.sendto(f"IsAttacking:{player_id}".encode(), server_address)
            attack_rect = pygame.Rect(player_x, player_y, image_paths[player_id][3][0], image_paths[player_id][3][1])
            opponent_rect = pygame.Rect(opponent_x, opponent_y, opponent_width, opponent_height)
            if attack_rect.colliderect(opponent_rect):
                client_socket.sendto(f"HIT:{opponent_id}".encode(), server_address)

        velocity_y += gravity
        player_y += velocity_y

        if player_y >= screen_height - ground_height - player_height:
            player_y = screen_height - ground_height - player_height
            velocity_y = 0
            on_ground = True

        future_y = player_y + velocity_y
        future_rect = pygame.Rect(player_x, future_y, player_width, player_height)
        for platform in platforms:
            if future_rect.colliderect(platform) and velocity_y >= 0:
                player_y = platform.top - player_height
                velocity_y = 0
                on_ground = True
                break

        frame_count += 1
        if frame_count % 2 == 0:
            client_socket.sendto(f"POSITION:{player_x},{player_y}".encode(), server_address)
            client_socket.sendto(f"HEALTH:{player_health}".encode(), server_address)

        if is_attacking:
            screen.blit(player_attack_image, (player_x, player_y))
            attack_timer -= 1
            if attack_timer <= 0:
                is_attacking = False
        else:
            screen.blit(player_image, (player_x, player_y))

        screen.blit(opponent_image, (opponent_x, opponent_y))

        if player_health <= 0:
            running = False

        for platform in platforms:
            pygame.draw.rect(screen, platform_color, platform)

        if waiting_for_other:
            wait_font = pygame.font.SysFont('Arial', 32, bold=True)
            wait_text = wait_font.render("Waiting for other player...", True, (255, 255, 255))
            text_rect = wait_text.get_rect(center=(screen_width // 2, 30))
            pygame.draw.rect(screen, (0, 0, 0), text_rect.inflate(20, 10))
            screen.blit(wait_text, text_rect)

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

    pygame.quit()
    show_game_over_screen(player_id)

def show_game_over_screen(player_id):
    import pygame
    pygame.init()
    screen_width, screen_height = 960, 540
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption("GAME OVER")

    game_over_img = pygame.image.load("game_over.jpg")
    game_over_img = pygame.transform.scale(game_over_img, (screen_width, screen_height))

    font_button = pygame.font.SysFont("Arial", 48, bold=True)
    font_title = pygame.font.SysFont("Arial", 72, bold=True)

    restart_rect = pygame.Rect(screen_width // 2 - 100, 330, 200, 60)
    quit_rect = pygame.Rect(screen_width // 2 - 100, 430, 200, 60)

    def draw_button(rect, text, hovered):
        base_color = (255, 255, 255) if hovered else (220, 220, 220)
        glow_color = (255, 215, 0) if hovered else (100, 100, 100)
        text_color = (0, 0, 0)

        pygame.draw.rect(screen, (50, 50, 50), rect.move(3, 3), border_radius=12)
        pygame.draw.rect(screen, glow_color, rect.inflate(12, 12), border_radius=16)
        pygame.draw.rect(screen, base_color, rect, border_radius=12)

        button_text = font_button.render(text, True, text_color)
        button_rect = button_text.get_rect(center=rect.center)
        screen.blit(button_text, button_rect)

    running = True
    while running:
        screen.blit(game_over_img, (0, 0))

        mouse_pos = pygame.mouse.get_pos()
        hovered_restart = restart_rect.collidepoint(mouse_pos)
        hovered_quit = quit_rect.collidepoint(mouse_pos)

        draw_button(restart_rect, "Restart", hovered_restart)
        draw_button(quit_rect, "Quit", hovered_quit)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if hovered_restart:
                    running = False
                    pygame.quit()
                    run_game(player_id)
                    return
                elif hovered_quit:
                    running = False
                    pygame.quit()
                    sys.exit()

        pygame.display.update()

if __name__ == "__main__":
    player_id = sys.argv[1] if len(sys.argv) > 1 else "blue"
    run_game(player_id)
