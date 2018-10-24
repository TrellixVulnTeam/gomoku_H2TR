#!/usr/bin/env python

from __future__ import print_function, division
import itertools, time, copy
import collections, random
import os, pickle
import numba
import numpy as np
import tflearn

board_size = 15
estimate_level = 3
def strategy(state):
    """ AI's strategy

    Information provided to you:

    state = (board, last_move, playing, board_size)
    board = (x_stones, o_stones)
    stones is a set contains positions of one player's stones. e.g.
        x_stones = {(8,8), (8,9), (8,10), (8,11)}
    playing = 0|1, the current player's index

    Your strategy will return a position code for the next stone, e.g. (8,7)

    """

    board, last_move, playing, board_size = state
    strategy.playing = playing

    other_player = int(not playing)
    my_stones = board[playing]
    opponent_stones = board[other_player]

    if playing == 0: # if i'm black
        strategy.learndata = strategy.black_learndata
        strategy.opponent_learndata = strategy.white_learndata
    else:
        strategy.learndata = strategy.white_learndata
        strategy.opponent_learndata = strategy.black_learndata

    # swap start should always have some stones
    assert last_move != None
    # build state
    state = np.zeros(board_size**2, dtype=np.int8).reshape(board_size, board_size)
    for i,j in my_stones:
        state[i-1,j-1] = 1
    for i,j in opponent_stones:
        state[i-1,j-1] = -1

    oppo_state_id = state.tobytes()
    # clear the U cache
    U_stone.cache = dict()
    alpha = -2.0
    beta = 2.0
    empty_spots_left = np.sum(state==0)
    start_level = -1
    best_move, best_q = best_action_q(state, empty_spots_left, last_move, alpha, beta, 1, start_level)

    if oppo_state_id not in strategy.opponent_learndata and best_q != None:
        strategy.opponent_learndata[oppo_state_id] = [state.copy(), -best_q, 1]

    state[best_move] = 1
    state_id = state.tobytes()
    # store the win rate of this move
    if state_id not in strategy.learndata and best_q != None:
        strategy.learndata[state_id] = [state.copy(), best_q, 1]
    game_finished = False
    new_u = 0
    if i_win(state, best_move, 1):
        new_u = 1.0
        game_finished = True
    elif i_lost(state, 1):
        new_u = -1.0
        game_finished = True
    elif empty_spots_left <= 2:
        new_u = 0.0
        game_finished = True

    if strategy.started_from_beginning is True:
        if game_finished:
            if new_u != 1.0: # we don't learn winning games here
                discount = 0.9
                #discount_factor = 0.9
                for prev_state_id in strategy.hist_states[::-1]:
                    st, u, n_visited = strategy.learndata[prev_state_id]
                    n_visited += 1
                    new_u = u + discount * (new_u - u) / (n_visited**0.7) # this is the learning rate
                    strategy.learndata[prev_state_id] = st, new_u, n_visited
                    print("Updated U from %f to %f"%(u, new_u))
                    #discount *= discount_factor
                # also update the strategy.opponent_learndata to be negative u of mine
                for prev_state_id, prev_opponent_state_id in zip(strategy.hist_states[::-1], strategy.oppo_hist_states[::-1]):
                    _ , u, n_visited = strategy.learndata[prev_state_id]
                    old_u = strategy.opponent_learndata[prev_opponent_state_id][1]
                    strategy.opponent_learndata[prev_opponent_state_id] = None, -u, n_visited # we only use the u value here
                    print('Updated opponent U from %f to %f' %(old_u, -u))
                print("Updated win rate of %d states" % (len(strategy.hist_states)-1))
                pickle.dump(strategy.black_learndata, open('strategy.black_learndata','wb'))
                pickle.dump(strategy.white_learndata, open('strategy.white_learndata','wb'))
                print("Saved %d strategy.black_learndata to disk" % len(strategy.black_learndata))
                print("Saved %d strategy.white_learndata to disk" % len(strategy.white_learndata))
            strategy.started_from_beginning = False # we only update once
        elif best_q != None:
            # record the history states (initialized in the reset() function)
            strategy.hist_states.append(state_id)
            strategy.oppo_hist_states.append(oppo_state_id)
    # return the best move
    return ((best_move[0]+1, best_move[1]+1), best_q)



level_max_n = [50, 50, 50, 50, 20, 20, 15, 15]
def best_action_q(state, empty_spots_left, last_move, alpha, beta, player, level):
    "Return the optimal action for a state"
    if empty_spots_left == 0: # Board filled up, it's a tie
        return None, 0.0
    #move_interest_values = np.zeros(board_size**2, dtype=np.float32).reshape(board_size,board_size)
    move_interest_values = best_action_q.move_interest_values
    move_interest_values.fill(0) # reuse the same array
    # boost the interests of closer moves by a little bit
    # note that it might boost a taken spot, but an available spot will at least get 10 interest in find_interesting_moves()
    boost_dist = 3
    r, c = last_move
    xmin = max(0, r-boost_dist)
    xmax = min(board_size, r+boost_dist+1)
    ymin = max(0, c-boost_dist)
    ymax = min(board_size, c+boost_dist+1)
    move_interest_values[xmin:xmax, ymin:ymax] = 1.5
    move_interest_values[5:10,5:10] = 10.0

    is_first_move = False
    if level == -1:
       is_first_move = True
       level = 0

    verbose = False

    n_moves = 40 if empty_spots_left > 210 else 20
    interested_moves = find_interesting_moves(state, empty_spots_left, move_interest_values, player, n_moves, verbose)

    if len(interested_moves) == 1:
        current_move = interested_moves[0]
        current_move = (current_move[0], current_move[1])
        if is_first_move:
            q = Q_stone(state, empty_spots_left, current_move, alpha, beta, player, level+1)
        else:
            q = Q_stone(state, empty_spots_left, current_move, alpha, beta, player, level)
        return current_move, q

    best_move = (interested_moves[0,0], interested_moves[0,1]) # continue to play even I'm losing

    if player == 1:
        max_q = -1.0
        for current_move in interested_moves:
            current_move = (current_move[0], current_move[1]) # convert into tuple
            q = Q_stone(state, empty_spots_left, current_move, alpha, beta, player, level+1)
            if q > alpha: alpha = q
            if q > max_q:
                max_q = q
                best_move = current_move
            if max_q >= 1.0 or beta <= alpha:
                break
        best_q = max_q
    elif player == -1:
        min_q = 1.0
        for current_move in interested_moves:
            current_move = (current_move[0], current_move[1])
            q = Q_stone(state, empty_spots_left, current_move, alpha, beta, player, level+1)
            if q < beta: beta = q
            if q < min_q:
                min_q = q
                best_move = current_move
            if q <= -1.0 or beta <= alpha:
                break
        best_q = min_q
    return best_move, best_q

def Q_stone(state, empty_spots_left, current_move, alpha, beta, player, level):
    # update the state
    state[current_move] = player
    result = U_stone(state, empty_spots_left-1, current_move, alpha, beta, player, level)
    # revert the changes for the state
    state[current_move] = 0
    return result

def U_stone(state, empty_spots_left, last_move, alpha, beta, player, level):
    state_id = state.tobytes()
    if i_will_win(state, last_move, player):
        result = 1.0 if player == 1 else -1.0
    elif level >= estimate_level:
        ts = np.zeros((15,15), dtype=np.int8)
        ts[(7,9,7,6,6,7,8), (5,5,7,8,9,8,5)] = (1,1,1,-1,-1,-1,1)
        if np.array_equal(state,ts):
            import IPython
            IPython.embed()
        try:
            if player == 1:
                return strategy.learndata[state_id][1]
            else:
                return -strategy.opponent_learndata[state_id][1]
        except:
            pass
        try:
            return U_stone.cache[state_id]
        except:
            pass
        result = tf_predict_u(state, empty_spots_left, last_move, player)
    else:
        best_move, best_q = best_action_q(state, empty_spots_left, last_move, alpha, beta, -player, level)
        result = best_q
    U_stone.cache[state_id] = result
    return result

def tf_predict_u(state, empty_spots_left, last_move, player):
    "Generate the best moves, use the neural network to predict U, return the max U"
    if empty_spots_left == 0: # Board filled up, it's a tie
        return 0.0
    move_interest_values = best_action_q.move_interest_values
    move_interest_values.fill(0) # reuse the same array

    next_player = -player
    n_moves = 40 if empty_spots_left > 210 else 20
    interested_moves = find_interesting_moves(state, empty_spots_left, move_interest_values, next_player, n_moves)
    # make sure we solve all the hard 4 so that there're more than one interested_moves
    # avoid changing the original state
    next_state = state.copy() if len(interested_moves) == 1 else state
    while len(interested_moves) == 1:
        next_move = interested_moves[0]
        next_move = (next_move[0], next_move[1])
        # update the state
        next_state[next_move] = next_player
        next_state_id = next_state.tobytes()
        empty_spots_left -= 1
        if empty_spots_left <= 1:
            return 0 # it's a tie
        # check if this is a win state
        if i_will_win(next_state, next_move, next_player):
            result = 1.0 if next_player == 1 else -1.0
            return result
        # check if we learned this state before
        try:
            if next_player == 1:
                return strategy.learndata[next_state_id][1]
            else:
                return -strategy.opponent_learndata[next_state_id][1]
        except KeyError:
            pass
        try:
            return U_stone.cache[next_state_id]
        except:
            pass
        # if we reach here, it's time to go one more step
        next_player = -next_player
        move_interest_values.fill(0)
        interested_moves = find_interesting_moves(next_state, empty_spots_left, move_interest_values, next_player, n_moves)

    # find the known moves among interested_moves
    tf_moves, move_state_ids = [], []
    max_q = -1.0
    learndata = strategy.learndata if next_player == 1 else strategy.opponent_learndata
    for this_move in interested_moves:
        this_move = (this_move[0], this_move[1])
        next_state[this_move] = next_player
        this_state_id = next_state.tobytes()
        next_state[this_move] = 0
        try:
            max_q = max(max_q, learndata[this_state_id][1])
        except KeyError:
            try:
                max_q = max(max_q, tf_predict_u.cache[this_state_id])
            except KeyError:
                tf_moves.append(this_move)
                move_state_ids.append(this_state_id)

    # run tensorflow to evaluate all unknown moves and find the largest q
    n_tf = len(tf_moves)
    if n_tf > 0:
        all_interest_states = tf_predict_u.all_interest_states[:n_tf] # we only need a slice of the big array
        if next_player == -1: # if next is opponent
            all_interest_states[:,:,:,0] = (next_state == -1)
            all_interest_states[:,:,:,1] = (next_state == 1)
            all_interest_states[:,:,:,2] = 1 if strategy.playing == 1 else 0 # if I'm white, next player is black
        elif next_player == 1: # if next is me
            all_interest_states[:,:,:,0] = (next_state == 1)
            all_interest_states[:,:,:,1] = (next_state == -1)
            all_interest_states[:,:,:,2] = 1 if strategy.playing == 0 else 0 # if I'm black, next is me so black
        for i,current_move in enumerate(tf_moves):
            ci, cj = current_move
            all_interest_states[i,ci,cj,0] = 1 # put current move down
        predict_y = tf_predict_u.model.predict(all_interest_states)
        predict_y = np.array(predict_y).flatten()
        # store the computed y
        for sid, y in zip(move_state_ids, predict_y):
            tf_predict_u.cache[sid] = y
        tf_y = np.max(predict_y)
        max_q = max(max_q, tf_y)
    return max_q * next_player # if next_player is opponent, my win rate is negative of his


@numba.jit(nopython=True, nogil=True)
def find_interesting_moves(state, empty_spots_left, move_interest_values, player, n_moves, verbose=False):
    """ Look at state and find the interesing n_move moves.
    input:
    -------
    state: numpy.array board_size x board_size
    empty_spots_left: number of empty spots on the board
    player: 1 or -1, the current player
    n_moves: int, desired number of interesing moves

    output:
    -------
    interested_moves: numpy.array final_n_moves x 2
        *note : final_n_moves = 1 if limited
        *       else final_n_moves = n_moves + number of length-4 moves
        *note2: final_n_moves will not exceed empty_spots_left

    #suggested_n_moves: suggested number of moves to
    """
    force_to_block = False
    exist_will_win_move = False
    directions = ((1,1), (1,0), (0,1), (1,-1))
    final_single_move = np.zeros(2, dtype=np.int8).reshape(1,2) # for returning the single move
    for r in range(board_size):
        for c in range(board_size):
            if state[r,c] != 0: continue
            interest_value = 10 # as long as it's a valid point, this is for avoiding the taken spaces
            my_hard_4 = 0
            for dr, dc in directions:
                my_line_length = 1 # last_move
                opponent_line_length = 1
                # try to extend in the positive direction (max 5 times to check overline)
                ext_r = r
                ext_c = c
                skipped_1 = 0
                my_blocked = False
                opponent_blocked = False
                for i in range(5):
                    ext_r += dr
                    ext_c += dc
                    if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                        break
                    elif state[ext_r, ext_c] == player:
                        if my_blocked is True:
                            break
                        else:
                            my_line_length += 1
                            opponent_blocked = True
                    elif state[ext_r, ext_c] == -player:
                        if opponent_blocked is True:
                            break
                        else:
                            opponent_line_length += 1
                            my_blocked = True
                    else:
                        if skipped_1 is 0:
                            skipped_1 = i + 1 # allow one skip and record the position of the skip
                        else:
                            # peek at the next one and if it might be useful, add some interest
                            if ((state[ext_r+dr, ext_c+dc] == player) and (my_blocked is False)) or ((state[ext_r+dr, ext_c+dc] == -player) and (opponent_blocked is False)):
                                interest_value += 15
                            break

                # the backward counting starts at the furthest "unskipped" stone
                forward_my_open = False
                forward_opponent_open = False
                if skipped_1 == 0:
                    my_line_length_back = my_line_length
                    opponent_line_length_back = opponent_line_length
                elif skipped_1 == 1:
                    my_line_length_back = 1
                    opponent_line_length_back = 1
                    forward_my_open = True
                    forward_opponent_open = True
                else:
                    if my_blocked is False:
                        my_line_length_back = skipped_1
                        opponent_line_length_back = 1
                        forward_my_open = True
                    else:
                        my_line_length_back = 1
                        opponent_line_length_back = skipped_1
                        forward_opponent_open = True
                my_line_length_no_skip = my_line_length_back
                opponent_line_length_no_skip = opponent_line_length_back

                # backward is a little complicated, will try to extend my stones first
                ext_r = r
                ext_c = c
                skipped_2 = 0
                opponent_blocked = False
                for i in range(6-my_line_length_no_skip):
                    ext_r -= dr
                    ext_c -= dc
                    if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                        break
                    elif state[ext_r, ext_c] == player:
                        my_line_length_back += 1
                        opponent_blocked = True
                    elif state[ext_r, ext_c] == -player:
                        break
                    else:
                        if skipped_2 is 0:
                            skipped_2 = i + 1
                        else:
                            # peek at the next one and if it might be useful, add some interest
                            if state[ext_r-dr, ext_c-dc] == player:
                                interest_value += 15
                            break

                # see if i'm winning
                if my_line_length_back == 5:
                    # if there are 5 stones in backward counting, and it's not skipped in the middle
                    if skipped_2 == 0 or skipped_2 == (6-my_line_length_no_skip):
                        # i will win with this move, I will place the stone
                        final_single_move[0,0] = r
                        final_single_move[0,1] = c
                        return final_single_move

                # extend my forward line length to check if there is hard 4
                if skipped_2 is 0:
                    my_line_length += my_line_length_back - my_line_length_no_skip
                else:
                    my_line_length += skipped_2 - 1

                backward_my_open = True if skipped_2 > 0 else False
                backward_opponent_open = False
                # then try to extend the opponent
                if opponent_blocked is True:
                    if skipped_2 == 1:
                        backward_opponent_open = True
                    skipped_2 = 0 # reset the skipped_2 here to enable the check of opponent 5 later
                else:
                    ext_r = r
                    ext_c = c
                    skipped_2 = 0
                    for i in range(6-opponent_line_length_no_skip):
                        ext_r -= dr
                        ext_c -= dc
                        if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                            break
                        elif state[ext_r, ext_c] == player:
                            break
                        elif state[ext_r, ext_c] == -player:
                            opponent_line_length_back += 1
                        else:
                            if skipped_2 is 0:
                                skipped_2 = i + 1
                            else:
                                # peek at the next one and if it might be useful, add some interest
                                if state[ext_r-dr, ext_c-dc] == -player:
                                    interest_value += 15
                                break
                    # extend opponent forward line length to check if there is hard 4
                    if skipped_2 is 0:
                        opponent_line_length += opponent_line_length_back - opponent_line_length_no_skip
                    else:
                        opponent_line_length += skipped_2 - 1
                        backward_opponent_open = True
                        # here if opponent_line_length_back == 5, skipped_2 will be 0 and this flag won't be True
                        # but it do not affect our final result, because we have to block this no matter if it's open

                # check if we have to block this
                if opponent_line_length_back == 5:
                    if (skipped_2 == 0) or (skipped_2 == 6-opponent_line_length_no_skip):
                        final_single_move[0,0] = r
                        final_single_move[0,1] = c
                        force_to_block = True
                if force_to_block is False:
                    # if I will win after this move, I won't consider other moves
                    if forward_my_open is True and my_line_length == 4:
                        my_hard_4 += 1
                    if backward_my_open is True and my_line_length_back == 4:
                        my_hard_4 += 1
                    if my_hard_4 >= 2:
                        final_single_move[0,0] = r
                        final_single_move[0,1] = c
                        exist_will_win_move = True
                if force_to_block is False and exist_will_win_move is False:
                    # compute the interest_value for other moves
                    # if any line length >= 5, it's an overline so skipped
                    if (forward_my_open is True) and (my_line_length < 5):
                        interest_value += my_line_length ** 4
                    if (backward_my_open is True) and (my_line_length_back < 5):
                        interest_value += my_line_length_back ** 4
                    if (forward_opponent_open is True) and (opponent_line_length < 5):
                        interest_value += opponent_line_length ** 4
                    if (backward_opponent_open is True) and (opponent_line_length_back < 5):
                        interest_value += opponent_line_length_back ** 4
            # after looking at all directions, record the total interest_value of this move
            move_interest_values[r, c] += interest_value
            if interest_value > 256: # one (length_4) ** 4, highly interesting move
                n_moves += 1

    # all moves have been investigated now see if we have to block first
    if force_to_block is True or exist_will_win_move is True:
        if verbose is True:
            print(final_single_move[0,0], final_single_move[0,1], "Only One")
        return final_single_move
    else:
        flattened_interest = move_interest_values.ravel()
        # The interest value > 250 means at least one length_4 or three length_3 which make it highly interesting
        #n_high_interest_moves = np.sum(flattened_interest > 266) # did it in the loop
        if n_moves > empty_spots_left:
            n_moves = empty_spots_left
        high_interest_idx = np.argsort(flattened_interest)[-n_moves:][::-1]
        interested_moves = np.empty(n_moves*2, dtype=np.int8).reshape(n_moves, 2)
        interested_moves[:,0] = high_interest_idx // board_size
        interested_moves[:,1] = high_interest_idx % board_size

        if verbose is True:
            print("There are", n_moves, "interested_moves")
            for i in range(n_moves):
                print(interested_moves[i,0],interested_moves[i,1],'  :  ', flattened_interest[high_interest_idx[i]])
        return interested_moves


@numba.jit(nopython=True,nogil=True)
def i_win(state, last_move, player):
    """ Return true if I just got 5-in-a-row with last_move """
    r, c = last_move
    # try all 4 directions, the other 4 is included
    directions = [(1,1), (1,0), (0,1), (1,-1)]
    for dr, dc in directions:
        line_length = 1 # last_move
        # try to extend in the positive direction (max 4 times)
        ext_r = r
        ext_c = c
        for _ in range(5):
            ext_r += dr
            ext_c += dc
            if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                break
            elif state[ext_r, ext_c] == player:
                line_length += 1
            else:
                break
        if line_length is 6:
            continue
        # try to extend in the opposite direction
        ext_r = r
        ext_c = c
        for _ in range(6-line_length):
            ext_r -= dr
            ext_c -= dc
            if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                break
            elif state[ext_r, ext_c] == player:
                line_length += 1
            else:
                break
        if line_length is 5:
            return True # 5 in a row
    return False

@numba.jit(nopython=True,nogil=True)
def i_lost(state, player):
    for r in range(board_size):
        for c in range(board_size):
            if state[r,c] == 0 and i_win(state, (r,c), -player):
                return True
    return False

@numba.jit(nopython=True,nogil=True)
def i_will_win(state, last_move, player):
    """ Return true if I will win next step if the opponent don't have 4-in-a-row.
    Winning Conditions:
        1. 5 in a row.
        2. 4 in a row with both end open. (free 4)
        3. 4 in a row with one missing stone x 2 (hard 4 x 2)
     """
    r, c = last_move
    # try all 4 directions, the other 4 is equivalent
    directions = [(1,1), (1,0), (0,1), (1,-1)]
    n_hard_4 = 0 # number of hard 4s found
    for dr, dc in directions:
        line_length = 1 # last_move
        # try to extend in the positive direction (max 5 times to check overline)
        ext_r = r
        ext_c = c
        skipped_1 = 0
        for i in range(5):
            ext_r += dr
            ext_c += dc
            if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                break
            elif state[ext_r, ext_c] == player:
                line_length += 1
            elif skipped_1 is 0 and state[ext_r, ext_c] == 0:
                skipped_1 = i+1 # allow one skip and record the position of the skip
            else:
                break
        # try to extend in the opposite direction
        ext_r = r
        ext_c = c
        skipped_2 = 0
        # the backward counting starts at the furthest "unskipped" stone
        if skipped_1 is not 0:
            line_length_back = skipped_1
        else:
            line_length_back = line_length
        line_length_no_skip = line_length_back
        for i in range(6-line_length_back):
            ext_r -= dr
            ext_c -= dc
            if ext_r < 0 or ext_r >= board_size or ext_c < 0 or ext_c >= board_size:
                break
            elif state[ext_r, ext_c] == player:
                line_length_back += 1
            elif skipped_2 is 0 and state[ext_r, ext_c] == 0:
                skipped_2 = i + 1
            else:
                break

        if line_length_back == 6:
            # we found 6 stones in a row, this is overline, skip this entire line
            continue
        elif line_length_back == 5:
            if (skipped_2 == 0) or (skipped_2 == (6-line_length_no_skip)):
                # we found 5 stones in a row, because the backward counting is not skipped in the middle
                return True
                # else there is an empty spot in the middle of 6 stones, it's not a hard 4 any more
        elif line_length_back == 4:
            # here we have only 4 stones, if skipped in back count, it's a hard 4
            if skipped_2 is not 0:
                n_hard_4 += 1 # backward hard 4
                if n_hard_4 == 2:
                    return True # two hard 4
        # here we check if there's a hard 4 in the forward direction
        # extend the forward line to the furthest "unskipped" stone
        if skipped_2 == 0:
            line_length += line_length_back - line_length_no_skip
        else:
            line_length += skipped_2 - 1
        # hard 4 only if forward length is 4, if forward reaches 5 or more, it's going to be overline
        if line_length == 4 and skipped_1 is not 0:
            n_hard_4 += 1 # forward hard 4
            if n_hard_4 == 2:
                return True # two hard 4 or free 4
    return False



def initialize():

    if not hasattr(best_action_q, 'move_interest_values'):
        best_action_q.move_interest_values = np.zeros(board_size**2, dtype=np.float32).reshape(board_size,board_size)

    if not hasattr(strategy, 'black_learndata'):
        if os.path.isfile('strategy.black_learndata'):
            strategy.black_learndata = pickle.load(open('strategy.black_learndata','rb'))
            print("strategy.black_learndata found, loaded %d data" % len(strategy.black_learndata))
        else:
            strategy.black_learndata = dict()

    if not hasattr(strategy, 'white_learndata'):
        if os.path.isfile('strategy.white_learndata'):
            strategy.white_learndata = pickle.load(open('strategy.white_learndata','rb'))
            print("strategy.white_learndata found, loaded %d data" % len(strategy.white_learndata))
        else:
            strategy.white_learndata = dict()

    reset()

    if not hasattr(tf_predict_u, 'all_interest_states'):
        tf_predict_u.all_interest_states = np.zeros(board_size**4 * 3, dtype=np.int8).reshape(board_size**2, board_size, board_size, 3)

    if not hasattr(tf_predict_u, 'cache'):
        tf_predict_u.cache = dict()

def reset():
    """ reset the AI, clean history states """
    strategy.started_from_beginning = True
    strategy.hist_states = []
    strategy.oppo_hist_states = []

def board_show(stones):
    if isinstance(stones, np.ndarray):
        stones = {(s1,s2) for s1, s2 in stones}
    print(' '*4 + ' '.join([chr(97+i) for i in xrange(board_size)]))
    print (' '*3 + '='*(2*board_size))
    for x in xrange(1, board_size+1):
        row = ['%2s|'%x]
        for y in xrange(1, board_size+1):
            if (x-1,y-1) in stones:
                c = 'x'
            else:
                c = '-'
            row.append(c)
        print (' '.join(row))

def print_state(state):
    assert isinstance(state, np.ndarray)
    print(' '*4 + ' '.join([chr(97+i) for i in xrange(board_size)]))
    print (' '*3 + '='*(2*board_size))
    for x in xrange(1, board_size+1):
        row = ['%2s|'%x]
        for y in xrange(1, board_size+1):
            if state[x-1,y-1] == 1:
                c = 'x'
            elif state[x-1,y-1] == -1:
                c = 'o'
            else:
                c = '-'
            row.append(c)
        print (' '.join(row))


def test():
    initialize()
    state = np.zeros(board_size**2, dtype=np.int8).reshape(board_size, board_size)
    state[(9,10,11),(11,12,13)] = 1
    state[(6,8,9,11),(7,9,10,12)] = -1
    lastmove = (8,9)
    print_state(state)
    find_interesting_moves(state, 210, best_action_q.move_interest_values, player=1, n_moves=20, verbose=True)


def draw_state(state):
    board_size = 15
    print(' '*4 + ' '.join([chr(97+i) for i in xrange(board_size)]))
    print (' '*3 + '='*(2*board_size))
    me = state[0,0,2]
    for x in xrange(1, board_size+1):
        row = ['%2s|'%x]
        for y in xrange(1, board_size+1):
            if state[x-1,y-1,0] == 1:
                c = 'x' if me == 1 else 'o'
            elif state[x-1,y-1,1] == 1:
                c = 'o' if me == 1 else 'x'
            else:
                c = '-'
            row.append(c)
        print (' '.join(row))

if __name__ == '__main__':
    #import pickle
    #state = pickle.load(open('debug.state','rb'))
    #board, last_move, playing, board_size = state
    #player_stones = board[playing]
    #other = int(not playing)
    #ai_stones = board[other]
    #player_move = (8,9)
    #player_stones.add(player_move)
    #state = (player_stones, ai_stones), player_move, other, board_size
    #strategy(state)
    test()
