#!/usr/bin/env python

from __future__ import division
from Xlib import display, X
from PIL import Image
import time, random
import pyautogui

pyautogui.PAUSE = 0.1
pyautogui.FAILSAFE = True

class ScreenShot(object):
    """ This class can help quickly update a screenshot of certain region """
    @property
    def center(self):
        return int(0.5*(self.x2-self.x1)), int(0.5*(self.y2-self.y1))

    @property
    def border(self):
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def height(self):
        return self.y2 - self.y1

    def __init__(self, border=None):
        self.screen = display.Display().screen()
        self.root = self.screen.root
        self.update_border(border)

    def update_border(self, border):
        if border != None:
            self.x1, self.y1, self.x2, self.y2 = map(int, border)
            assert self.x2 > self.x1 and self.y2 > self.y1
        else:
            self.x1 = self.y1 = 0
            self.x2 = self.screen.width_in_pixels
            self.y2 = self.screen.height_in_pixels

    def capture(self):
        ''' A faster screen capture than the pyautogui.screenshot() '''
        raw = self.root.get_image(self.x1, self.y1, self.width, self.height, X.ZPixmap, 0xffffffff)
        image = Image.frombytes("RGB", (self.width, self.height), raw.data, "raw", "BGRX")
        return image

def read_game_state(scnshot):
    image = scnshot.capture()
    black_stones, white_stones = set(), set()
    board_size = 15
    shift_x, shift_y = (scnshot.width-1) / (board_size-1), (scnshot.height-1) / (board_size-1)
    last_move = None
    playing = 0
    black_color = (44, 44, 44)
    grey_color = (220, 220, 220)
    white_color = (243, 243, 243)
    deep_black = (39, 39, 39)
    red_color = (253, 23, 30)
    for ir in xrange(15): # row
        for ic in xrange(15): # column
            stone = (ir+1, ic+1) # in the AI we count stone position starting from 1
            pos = (int(shift_x * ic), int(shift_y * ir))
            color = image.getpixel(pos)
            if color == black_color or color == grey_color: # black stone
                black_stones.add(stone)
            elif color == white_color or color == deep_black: # white stone
                white_stones.add(stone)
            elif color == red_color: # red square means just played
                # check the color of the new position
                newpos = (pos[0]+15, pos[1]) if ic < 14 else (pos[0]-15, pos[1])
                newcolor = image.getpixel(newpos)
                if newcolor == black_color: # black stone
                    black_stones.add(stone)
                    playing = 1 # white is playing next
                elif newcolor == white_color: # white stone
                    white_stones.add(stone)
                    playing = 0 # black is playing next
                else:
                    print(newcolor)
                    raise RuntimeError("Error when getting last played stone color.")
                last_move = stone
    board = (black_stones, white_stones)
    state = (board, last_move, playing, board_size)
    return state

def place_stone(scnshot, move):
    x1, y1, x2, y2 = scnshot.border
    board_size = 15
    ir, ic = move
    shift_x, shift_y = (scnshot.width-1) / (board_size-1), (scnshot.height-1) / (board_size-1)
    x = x1 + shift_x * (ic-1)
    y = y1 + shift_y * (ir-1)
    pyautogui.moveTo(x, y, duration=0.1)
    pyautogui.click()
    time.sleep(0.2)

def play_one_move(scnshot, strategy, verbose=True):
    t_start = time.time()
    state = read_game_state(scnshot)
    total_stones = get_total_stones(state)
    if verbose:
        print("Current Game Board:")
        print_state(state)
        print("Calculating next move...")
    next_move, q = strategy(state)
    if verbose:
        winrate = ("%.1f%%" % ((q+1)/2*100)) if q != None else "??"
        print("Calculation finished. Playing (%d, %d) with win rate %s" % (next_move[0], next_move[1], winrate))
    place_stone(scnshot, next_move)
    t_end = time.time()
    time_spent = 0
    # check if this play is successful, return the real time_spent
    new_state = read_game_state(scnshot)
    if get_total_stones(new_state) > total_stones:
        time_spent = t_end - t_start
        time.sleep(0.5) # give the website 0.5 s to process
    # else, we will return 0
    return time_spent

def get_total_stones(state):
    black_stones, white_stones = state[0]
    return len(black_stones) + len(white_stones)

def print_state(state):
    board, last_move, playing, board_size = state
    print(' '*4 + ' '.join([chr(97+i) for i in range(board_size)]))
    print(' '*3 + '='*(2*board_size))
    for x in range(1, board_size+1):
        row = ['%2s|'%x]
        for y in range(1, board_size+1):
            if (x,y) in board[0]:
                c = 'x'
            elif (x,y) in board[1]:
                c = 'o'
            else:
                c = '-'
            if (x,y) == last_move:
                c = '\033[92m' + c + '\033[0m'
            row.append(c)
        print(' '.join(row))

def game_paused(scnshot):
    image = scnshot.capture()
    # find if the board is on the image
    found_board = False
    n_orange = 0
    board_color = (239, 175, 105)
    for x in range(5, 125, 10):
        for y in range(5, 125, 10):
            if image.getpixel((x,y)) == board_color:
                n_orange += 1
                if n_orange > 2:
                    found_board = True
        if found_board == True:
            break
    # if we don't find board in the image, return paused
    if found_board == False:
        return -1
    # check if the red bar is in the center
    cx, cy = scnshot.center
    n_red = 0
    red_color = (236,43,36)
    for x in range(cx-200, cx+200, 20):
        for y in range(cy-70, cy+70, 10):
            if image.getpixel((x,y)) == red_color:
                n_red += 1
                if n_red > 2:
                    return 1
    return 0

def check_me_playing(scnshot, maxtime=300):
    state = read_game_state(scnshot)
    board, last_move, playing, board_size = state
    if last_move != None: # if the opponent played
        return True
    else:
        return False

def click_start(scnshot):
    x1, y1, x2, y2 = scnshot.border
    cx, cy = scnshot.center
    white_color = (255,255,255)
    image = scnshot.capture()
    found_start = None
    for y in range(cy, cy+60, 5):
        if image.getpixel((cx,y)) == white_color:
            if image.getpixel((cx+40,y)) == white_color:
                if image.getpixel((cx+40,y+10)) == white_color:
                    found_start = (cx, y)
                    break
    game_started = False
    if found_start != None:
        x, y = found_start
        pyautogui.moveTo(x1+x, y1+y, duration=0.1)
        pyautogui.click()
        # wait for 10 s for opponent to click start
        for _ in xrange(22):
            time.sleep(0.2)
            if game_paused(scnshot) == False:
                game_started = True
                break
    return game_started

def detect_board_edge():
    try:
        x1, y1 = pyautogui.locateCenterOnScreen('top_left.png')[:2]
        x2, y2 = pyautogui.locateCenterOnScreen('bottom_right.png')[:2]
    except:
        raise RuntimeError("Board not found on the screen!")
    return x1, y1, x2, y2


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Player Gomoku on playok.com', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-t', '--time', default=5, type=int, help='Time limit in minutes')
    parser.add_argument('-l', '--level', default=3, type=int, help='Estimate Level')
    parser.add_argument('-d', '--detect', default=False, action='store_true', help='Detect game board at beginning')
    args = parser.parse_args()

    if args.detect:
        # detect the game board
        print("Detecting the game board...")
        x1, y1, x2, y2 = detect_board_edge()
    else:
        x1, y1, x2, y2 = (2186,237,3063,1114)
    print("Set board in the square (%d,%d) -> (%d,%d)" % (x1,y1,x2,y2))
    print("Please do not move game window from now on.")

    scnshot = ScreenShot(border=(x1,y1,x2,y2))
    # load the AI player
    import construct_dnn
    import player_AI
    model = construct_dnn.construct_dnn()
    model.load('tf_model')
    player_AI.tf_predict_u.model = model
    player_AI.initialize()

    time_spent = 0
    total_time = args.time * 60
    # loop to play multiple steps
    while True:
        try:
            time.sleep(0.5)
            status = game_paused(scnshot)
            if status == -1:
               continue
            elif status == 1:
                time.sleep(1)
                # try to click the start button
                if click_start(scnshot) == True:
                    # if game started, we check if we are the black first
                    time_spent = 0
                    player_AI.estimate_level = args.level
                    print("Game started with AI level = %d" % args.level)
                    # try to play one move as black
                    time_spent += play_one_move(scnshot, player_AI.strategy)
            else:
                # check if i'm playing, will wait here if not
                if check_me_playing(scnshot) == True:
                    time_spent += play_one_move(scnshot, player_AI.strategy)
                    # check how much time left
                    time_left = total_time - time_spent
                    print("Time Left: %02d:%02d " % divmod(time_left, 60))
                    tdown2 = min(total_time*0.6, 60)
                    if time_left < tdown2 and player_AI.estimate_level > 2:
                        print("Switching to fast mode, AI level = 2")
                        player_AI.estimate_level = 2
                    tdown1 = min(total_time*0.3, 30)
                    if time_left < tdown1 and player_AI.estimate_level > 1:
                        print("Switching to ultrafast mode, AI level = 1")
                        player_AI.estimate_level = 1
        except (KeyboardInterrupt, pyautogui.FailSafeException):
            new_total_time = raw_input("Stopped by user, enter new time limit in minutes, or enter to continue...")
            try:
                total_time = float(new_total_time) * 60
                print("New total time has been set to %.1f s" % total_time)
            except:
                pass

if __name__ == '__main__':
    main()
