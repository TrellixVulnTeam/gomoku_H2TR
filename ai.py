#!/usr/bin/env python

import itertools, time, copy
import collections, random
import os, pickle
import numba
import numpy as np

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
            return f(*args)
    _f.cache = cache
    return _f

def strategy(state):
    """ AI's strategy """

    """ Information provided to you:

    state = (board, last_move, playing, board_size)
    board = (x_stones, o_stones)
    stones is a set contains positions of one player's stones. e.g.
        x_stones = {(8,8), (8,9), (8,10), (8,11)}
    playing = 0|1, the current player's index

    Your strategy will return a position code for the next stone, e.g. (8,7)
    """
    global board_size
    global best_lv1
    global my_best_u

    global pruned, computed
    pruned, computed = 0, 0

    board, last_move, playing, board_size = state
    other_player = int(not playing)
    my_stones = board[playing]
    opponent_stones = board[other_player]
    # put the first stone in the center if it's the start of the game
    if len(my_stones) is 0 and len(opponent_stones) is 0:
        center = int((board_size+1)/2)
        return (center, center)

    state = (my_stones, opponent_stones)
    #key = (frozenset(my_stones), frozenset(opponent_stones))
    #if key in estimate_cache:
    #    best_lv1 = 1.0 - estimate_cache[key][1]
    #    print("best_lv1: %f"%best_lv1)
    #else:
    #    print("Haven't seen this state!")
    #    best_lv1 = 1.0
    my_best_u = 0.0 # reset
    best_move, max_q = best_action_q(state, 0)
    #print("Pruned: %d, Computed %d" %(pruned, computed))
    #print("best_lv1: %f"%best_lv1)
    return best_move

#estimate_cache = dict()
#best_lv1 = 0
#pruned = 0
#computed = 0
my_best_u = 0.0

def best_action_q(state, level):
    "Return the optimal action for a state"
    #global estimate_cache, best_lv1, pruned, computed
    my_stones, opponent_stones = state

    # look at previously estimated moves, if this move is not so good, skip it
    #key = (frozenset(my_stones), frozenset(opponent_stones))
    #if level == 1:
    #    try:
    #        best_move, max_q = estimate_cache[key]
    #        if max_q > 0.1 + best_lv1 or max_q == 1.0:
    #            pruned += 1
    #            print 'Pruned: ', state, "q: %.2f" % max_q
    #            return (best_move, max_q)
    #        else:
    #            computed += 1
    #    except:
    #        computed += 1
    #        pass

    max_q = 0
    best_move = (0,0) # admit defeat if all moves have 0 win rate
    all_stones = my_stones | opponent_stones
    possible_moves = available_positions(all_stones)

    for current_move in possible_moves:
        q = Q_stone(state, current_move, level)
        if q > max_q:
            max_q = q
            best_move = current_move
            if q == 1.0:
                break

    global my_best_u
    if level == 1:
        if max_q < 1.0 - my_best_u:
            my_best_u = 1.0 - max_q
    #    #print possible_moves
    #    #print state, "max_q:", max_q
    #    if max_q < best_lv1:
    #        best_lv1 = max_q

    ## store the max_q for this state
    #if 1 < level < 4:
    #    estimate_cache[key] = (best_move, max_q)

    return best_move, max_q

@numba.jit(nopython=True,nogil=True)
def available_positions(all_stones):
    positions = set()
    for x in range(1, board_size+1):
        for y in range(1, board_size+1):
            stone = (x,y)
            if stone not in all_stones and near_any_stone(stone, all_stones):
                positions.add(stone)
    return positions

@numba.jit(nopython=True,nogil=True)
def near_any_stone(last_move, all_stones):
    r1, c1 = last_move
    for r2, c2 in all_stones:
        if abs(r2-r1) < 2 and abs(c2-c1) < 2:
            return True
    return False

@numba.jit(nopython=True, nogil=True)
def nearby_avail_positions(this_stone, all_stones):
    """ Find available positions on the board that are adjacent to this_stone """
    r, c = this_stone
    result = set()
    nearby_pos = {(r-1,c-1), (r-1,c), (r-1,c+1), (r,c-1), (r,c+1), (r+1,c-1), (r+1,c), (r+1,c+1)}
    for stone in nearby_pos:
        if 0 < stone[0] <= board_size and 0 < stone[1] <= board_size and stone not in all_stones:
            result.add(stone)
    return result

@numba.jit(nopython=True, nogil=True)
def nearby_stones(this_stone):
    """ Find available positions on the board that are adjacent to this_stone """
    r, c = this_stone
    result = set()
    nearby_pos = {(r-1,c-1), (r-1,c), (r-1,c+1), (r,c-1), (r,c+1), (r+1,c-1), (r+1,c), (r+1,c+1)}
    for stone in nearby_pos:
        if 0 < stone[0] <= board_size and 0 < stone[1] <= board_size:
            result.add(stone)
    return result

def Q_stone(state, current_move, level):
    my_stones, opponent_stones = state
    new_my_stones = my_stones.copy()
    new_my_stones.add(current_move)
    state = (new_my_stones, opponent_stones)
    return U_stone(state, current_move, level)

def U_stone(state, last_move, level):
    my_stones, opponent_stones = state
    MC_start_level = 4
    #if level == 1:
    #    print my_stones, i_win(my_stones, last_move)

    global my_best_u

    if i_win(my_stones, last_move):
        result = 1.0
    else:
        # estimate current U
        estimate_u = MC_estimate_U(state, 15, 20)
        if level >= MC_start_level:
            return estimate_u
        elif level > 0:
            if level % 2 == 0: # if it's my turn, we need the max u
                if estimate_u + 0.2 < my_best_u: #if this is not good, stop here
                    print "my_best_u: ", my_best_u
                    print "Lv %d, Skipped: " %level, state, "estimate: %.4f" %estimate_u
                    return estimate_u
            else: #if it's opponent's turn, we want the min u
                if estimate_u - 0.2 > 1.0 - my_best_u:
                    print "my_best_u: ", my_best_u
                    print "Lv %d, Skipped: " %level, state, "estimate: %.4f" %estimate_u
                    return estimate_u
        # go to next level
        state = (opponent_stones, my_stones)
        best_move, max_q = best_action_q(state, level+1)
        result = 1.0 - max_q

    #elif level < MC_start_level:
    #    # go to the next player
    #    state = (opponent_stones, my_stones)
    #    best_move, max_q = best_action_q(state, level+1)
    #    result = 1.0 - max_q
    #elif level == MC_start_level:
    #    # launch Monte Carlo Tree Search
    #    result = MC_estimate_U(state, 15, 20)
    return result

@numba.jit(nopython=True, nogil=True)
def MC_estimate_U(state, n_MC, max_steps):
    """ Randomly put stones until the game ends, estimate the U based on number of games won. """
    my_stones, opponent_stones = state
    n_win = 0.0
    all_stones = my_stones | opponent_stones
    if len(all_stones) < 4: return 0.5
    all_possible_moves = available_positions(all_stones)
    for _ in range(n_MC):
        # pool of all available positions
        current_possible_moves = list(all_possible_moves)
        current_possible_moves_set = all_possible_moves.copy()
        current_all_stone = all_stones.copy()
        current_my_stone = my_stones.copy()
        current_opponent_stone = opponent_stones.copy()
        winning_player = 1
        max_i_move = len(current_possible_moves) - 1
        i_step = 0
        while True:
            # choose a random stone from the pool
            i_move = random.randint(0, max_i_move)
            random_move = current_possible_moves.pop(i_move)
            #random_move = current_possible_moves[i_move]
            current_possible_moves_set.remove(random_move)

            max_i_move -= 1
            # place that stone for the current player
            current_stones = current_my_stone if winning_player else current_opponent_stone
            current_stones.add(random_move)


            r, c = random_move
            nearby_stones = ((r-1,c-1), (r+1,c+1), (r-1,c), (r+1,c), (r-1,c+1), (r+1,c-1), (r,c-1), (r,c+1))
            winning = False
            tested = -1 # if the next stone is already tested (opposite side)
            for i_ns in range(8):
                ns = nearby_stones[i_ns]
                if ns in current_stones:
                    if i_ns == tested:
                        tested = -1
                    else:
                        if i_ns % 2 == 0:
                            tested = i_ns + 1 # skip the next nearby stone
                        nr, nc = ns
                        dx, dy = nr-r, nc-c
                        line_length = 2 # last_move and nearby_s
                        # try to extend in this direction
                        for i in range(1,4):
                            ext_stone = (nr+dx*i, nc+dy*i)
                            if ext_stone in my_stones:
                                line_length += 1
                            else:
                                break
                        # try to extend in the opposite direction
                        for i in range(1,4):
                            ext_stone = (r-dx*i, c-dy*i)
                            if ext_stone in my_stones:
                                line_length += 1
                            else:
                                break
                        if line_length >= 5:
                            winning = True
                            break
                else:
                    if ns not in current_possible_moves_set:
                        current_possible_moves_set.add(ns)
                        current_possible_moves.append(ns)
                        max_i_move += 1

            # check if game ends
            #if i_win(current_stones, random_move):
            if winning:
                n_win += winning_player
                break
            # prepare for the next round
            current_all_stone.add(random_move)
            #for ns in nearby_avail_positions(random_move, current_all_stone):
            #    if ns not in current_possible_moves:
            #        current_possible_moves.append(ns)
            #        max_i_move += 1
            if max_i_move == 0 or i_step > max_steps: # this is a tie
                n_win += 0.5
                break
            # goto next player
            winning_player = int(not winning_player)
            i_step += 1
    return n_win / n_MC



#@numba.jit(nopython=True, nogil=True)
#def min_stone_dist(last_move, all_stones):
#    r1, c1 = last_move
#    min_dist = board_size
#    for r2, c2 in all_stones:
#        dist = max(abs(r1-r2), abs(c1-c2))
#        if dist < min_dist:
#            min_dist = dist
#    return min_dist



def min_stone_dist(last_move, all_stones):
    return min(stone_dist(last_move, stone) for stone in all_stones)

@memo
def stone_dist(stone1, stone2):
    r1, c1 = stone1
    r2, c2 = stone2
    return max(abs(r1-r2), abs(c1-c2))

@numba.jit(nopython=True,nogil=True)
def i_win(my_stones, last_move):
    if len(my_stones) < 5: return False
    r, c = last_move
    # find any nearby stone
    nearby_stones = ((r-1,c-1), (r+1,c+1), (r-1,c), (r+1,c), (r-1,c+1), (r+1,c-1), (r,c-1), (r,c+1))
    #nearby_stones &= my_stones
    skip_next = False
    #for i_ns in range(8):
    i_ns = 0
    while True:
        if i_ns >= 8:
            break
        nearby_s = nearby_stones[i_ns]
        if nearby_s not in my_stones:
            i_ns += 1
            continue
        line_length = 2 # last_move and nearby_s
        nr, nc = nearby_s
        dx, dy = nr-r, nc-c
        # try to extend in this direction
        for i in range(1,4):
            ext_stone = (nr+dx*i, nc+dy*i)
            if ext_stone in my_stones:
                line_length += 1
            else:
                break
        # try to extend in the opposite direction
        for i in range(1,4):
            ext_stone = (r-dx*i, c-dy*i)
            if ext_stone in my_stones:
                line_length += 1
            else:
                break
        if line_length >= 5:
            return True
        i_ns += (2 - i_ns % 2) # the next one on the opposite side is already explored
    return False



def benchmark():
    assert i_win({(8, 9), (8, 11), (8, 8), (8, 10), (8, 12)}, (8,10)) == True
    my_stones = {(8,8),(8,9),(8,10),(8,11),(9,10),(11,12),(9,11),(9,12),(7,12)}
    last_move = (9,10)

    t0 = time.time()
    n_repeat = 100000*10
    for _ in xrange(n_repeat):
        i_win(my_stones, last_move)
    t1 = time.time()
    print("--- %f ms per i_win() call ---" %((t1-t0)*1000/n_repeat))

def test():
    ai_stones = {(8,7),(9,8),(10,9)}
    player_stones = {(8,8),(8,9),(8,10),(8,11)}
    board = (player_stones, ai_stones)
    playing = 1
    last_move = (8,11)
    state = (board, last_move, playing, 15)
    t0 = time.time()
    strategy(state)
    t1 = time.time()
    print("--- %f s  ---" %(t1-t0))

if __name__ == '__main__':
    import time
    test()
    #benchmark()
