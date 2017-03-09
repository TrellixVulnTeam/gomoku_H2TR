#!/usr/bin/env python
# -- coding: utf-8 --

#==========================
#=      Gomoku Game       =
#==========================

import os, sys, random, time, copy, collections
from functools import update_wrapper

def decorator(d):
    "Make function d a decorator: d wraps a function fn."
    def _d(fn):
        return update_wrapper(d(fn), fn)
    update_wrapper(_d, d)
    return _d

@decorator
def memo(f):
    """Decorator that caches the return value for each call to f(args).
    Then when called again with same args, we can just look it up."""
    cache = {}
    def _f(*args):
        try:
            return cache[args]
        except KeyError:
            cache[args] = result = f(*args)
            return result
        except TypeError:
            # some element of args refuses to be a dict key
            return f(args)
    _f.cache = cache
    return _f

@memo
def colored(s, color=''):
    if color.lower() == 'green':
        return '\033[92m' + s + '\033[0m'
    elif color.lower() == 'yellow':
        return '\033[93m' + s + '\033[0m'
    elif color.lower() == 'red':
        return '\033[91m' + s + '\033[0m'
    elif color.lower() == 'blue':
        return '\033[94m' + s + '\033[0m'
    elif color.lower() == 'bold':
        return '\033[1m' + s + '\033[0m'
    else:
        return s

class Gomoku(object):
    """ Gomoku Game Rules:
    Two players alternatively put their stone on the board. First one got five in a row wins.
    """

    def __init__(self, board_size=15, players=None, fastmode=False):
        print("*********************************")
        print("*      Welcome to Gomoku !      *")
        print("*********************************")
        print(self.__doc__)
        self.reset()
        self.board_size = board_size
        self.fastmode = fastmode
        self.playing = None
        self.players = [Player(player_name) for player_name in players]
        self.winning_stones = set()
        self.last_move = None

    @property
    def state(self):
        return (self.board, self.playing)

    def reset(self):
        self.board = (set(), set())

    def print_board(self):
        print ' '*4 + ' '.join([chr(97+i) for i in xrange(self.board_size)])
        print ' '*3 + '='*(2*self.board_size)
        for x in xrange(1, self.board_size+1):
            row = ['%2s|'%x]
            for y in xrange(1, self.board_size+1):
                if (x,y) in self.board[0]:
                    c = 'x'
                elif (x,y) in self.board[1]:
                    c = 'o'
                else:
                    c = '-'
                if (x,y) in self.winning_stones or (x,y) == self.last_move:
                    c = colored(c, 'green')
                row.append(c)
            print ' '.join(row)

    def play(self):
        if self.fastmode < 2:  print("Game Start!")
        i_turn = 0
        new_step = None
        while True:
            if self.fastmode < 2:  print("----- Turn %d -------" % i_turn)
            self.playing = i_turn % 2
            self.print_board()
            current_player = self.players[self.playing]
            if self.fastmode < 2: print("--- %s's turn ---" % current_player.name)
            max_try = 5
            for i_try in range(max_try):
                self.last_move = current_player.strategy(self.state)
                if self.place_stone():
                    break
                elif i_try == max_try-1:
                    if self.fastmode < 2: print("Player %s has made %d illegal moves, he lost."%(current_player.name, max_try))
                    other_player = int(not current_player)
                    winner = self.players[other_player].name
                    if self.fastmode < 2: print("Winner is %s"%winner)
                    return winner
            # check if current player wins
            winner = self.check_winner()
            if winner:
                self.print_board()
                if self.fastmode < 2:
                    print("##########    %s is the WINNER!    #########" % current_player.name)
                return winner
            elif i_turn == self.board_size ** 2 - 1:
                if self.fastmode < 2: print("This game is a tie!")
                return "Tie"
            i_turn += 1

    def place_stone(self):
        # check if this position is on the board
        r, c = self.last_move
        if r < 1 or r > self.board_size or c < 1 or c > self.board_size:
            print("This position is outside the board!")
            return False
        # check if this position is already taken
        taken_pos = self.board[0] | self.board[1]
        if self.last_move in taken_pos:
            print("This position is already taken!")
            return False
        else:
            self.board[self.playing].add(self.last_move)
            return True

    def check_winner(self):
        r, c = self.last_move
        my_stones = self.board[self.playing]
        # find any nearby stone
        nearby_stones = set()
        for x in range(max(r-1, 1), min(r+2, self.board_size+1)):
            for y in range(max(c-1, 1), min(c+2, self.board_size+1)):
                stone = (x,y)
                if stone in my_stones and (2*r-x, 2*c-y) not in nearby_stones:
                    nearby_stones.add(stone)
        for nearby_s in nearby_stones:
            winning_stones = {self.last_move, nearby_s}
            nr, nc = nearby_s
            dx, dy = nr-r, nc-c
            # try to extend in this direction
            for i in range(1,4):
                ext_stone = (nr+dx*i, nc+dy*i)
                if ext_stone in my_stones:
                    winning_stones.add(ext_stone)
                else:
                    break
            # try to extend in the opposite direction
            for i in range(1,5):
                ext_stone = (r-dx*i, c-dy*i)
                if ext_stone in my_stones:
                    winning_stones.add(ext_stone)
                else:
                    break
            if len(winning_stones) >= 5:
                self.winning_stones = winning_stones
                return self.players[self.playing].name
        return None

    def delay(self, n):
        """ Delay n seconds if not in fastmode"""
        if not self.fastmode:
            time.sleep(n)

    def get_strategy(self, p):
        return p.strategy(self.state)

class Player(object):
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        try:
            self._name = str(value)
        except:
            raise TypeError("Player Name must be a string.")

    def __repr__(self):
        return "Player %s"%self.name

    def __init__(self, name):
        self.name = name
        # Allow name to be appended by a number
        if (not name[0].isdigit()) and (name[-1].isdigit()):
            name = name[:-1]
        # search for the strategy file
        for f in os.listdir('.'):
            filename, fileext = os.path.splitext(f)
            if name.lower() == filename.lower() and fileext == '.py':
                print('strategy() found in %s, will use as AI.'%f)
                p = __import__(filename)
                try:
                    self.strategy = p.strategy
                except:
                    raise RuntimeError("Function strategy(state) is not found in %s"%filename)
                try:
                    self.finish = p.finish
                except:
                    pass
        # if not found, use manual input
        if not hasattr(self, 'strategy'):
            self.strategy = self.human_input

    def human_input(self, state):
        """ Ask player to place stone """
        s = raw_input('Please place stone, enter code like "8h":  ')
        r, c = s[:-1], s[-1]
        r = int(r)
        c = ord(c) - 96
        return (r,c)


def main():
    import argparse
    parser = argparse.ArgumentParser("Play the Gomoku Game!", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('players', nargs='*', default=['Player1', 'AI'], help='Names of Players, the first one plays first.')
    parser.add_argument('--board_size', type=int, default=15, help='Size of the board.')
    parser.add_argument('--fast', action='store_true', help='Run the game in fast mode.')
    parser.add_argument('-n', '--ngames', type=int, help='Play a number of games to gather statistics.')
    parser.add_argument('--fixorder', action='store_true', help='Fix the order of players in a multi-game series.')
    args = parser.parse_args()

    # fix the .py after player names
    players = []
    for p in args.players:
        players.append(p[:-3] if p.endswith('.py') else p)
    assert len(players) == 2, "Gomoku can only be played with 2 players."


    game = Gomoku(board_size=args.board_size, players=players, fastmode=args.fast)

    if args.ngames is None:
        game.play()
    else:
        # check if all players have stategy function setup
        for p in game.players:
            if p.strategy.__name__ == 'human_input':
                print("%s need a strategy function to enter the auto-play mode. Exiting.."%p.name)
                return
        print("Gathering result of %d games..."%args.ngames)
        game.fastmode = 2
        game_output = open('game_results.txt','w')
        winner_board = collections.OrderedDict([(p.name, 0) for p in game.players])
        def playone(i):
            game_output.write('Game %-4d .'%(i+1))
            game.reset()
            winner = game.play()
            for w in winners:
                winner_board[w] += 1
            game_output.write('Game %-4d: Winner is %s\n'%(i+1, winner))
            game_output.flush()
        for i in range(args.ngames):
            playone(i)
            # switch the order of the players
            if (i % 2) != 0 and not args.fixorder:
                game.players = game.players[1:] + [game.players[0]]
        game_output.close()
        print("Name    |   Games Won")
        for name, nwin in winner_board.items():
            print("%-7s | %7d"%(name, nwin))
    # Let the players finish their game
    for p in game.players:
        try:
            p.finish()
        except:
            pass

if __name__ == "__main__":
    main()
