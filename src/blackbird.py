import numpy as np
import random
from copy import deepcopy

from src.network import network
from src.mcts import mcts
from src.logger import *

def format2DArray(a):
    s = ''
    for r in range(a.shape[0]):
        s += '['
        for c in range(a.shape[1]):
            s += '{:<4.1f}'.format(a[r,c])
        s += ']\n'

    return s


class blackbird(logger):
    def __init__(self, game_framework, parameters):
        self.game_framework = game_framework
        self.parameters = parameters
        
        self.network = network(parameters['network'], load_old=True, writer=True)
        
        self.states = []
        self.move_probs = []
        self.rewards = []
      
        super().__init__(parameters.get('log_dir'))
        
    @canLog(log_file = 'selfPlay.txt')
    def selfPlay(self, num_games=1, show_game=False):
        """ Use the current network to generate test games for training.
        """
        for game_num in range(num_games):
            self.log('-'*20)
            self.log('New Game: {}'.format(game_num))
            
            new_game = self.game_framework()
            while not new_game.isGameOver():
                tree_search = mcts(new_game, self.network, self.parameters['mcts'])
                selected_move, move_probs = tree_search.getBestMove()
                self.__logMove(new_game, selected_move, move_probs)
                new_game.move(selected_move)
                
                self.states.append(np.append(
                    new_game.board,
                    np.array([[
                        [[new_game.player] for i in range(new_game.dim)]
                        for j in range(new_game.dim)]]),
                    axis=3))

                self.move_probs.append(move_probs)
                
                new_game.move(selected_move)
                if show_game:
                    new_game.dumpBoard()
                
            result = new_game.getResult()
            for state in self.states:
                player = state[0,0,0,2]
                if player == result:
                    reward = 1
                elif player == -result:
                    reward = -1
                else:
                    reward = 0
                
                self.rewards.append(reward)

    def train(self, learning_rate=0.01):
        """ Use the games generated from selfPlay() to train the network.
        """
        batch_size = self.parameters['network']['training']['batch_size']
        num_batches = round(len(self.states) / batch_size)

        for batch in range(num_batches):
            batch_indices = np.sort(np.random.choice(range(len(self.states)), batch_size, replace=False))[::-1]
            
            batch_states = np.vstack([self.states[ind] for ind in batch_indices])
            batch_move_probs = np.vstack([self.move_probs[ind] for ind in batch_indices])
            batch_rewards = np.array([self.rewards[ind] for ind in batch_indices])

            self.network.train(batch_states, batch_rewards, batch_move_probs, learning_rate=learning_rate)

            for index in batch_indices:
                self.states.pop(index)
                self.move_probs.pop(index)
                self.rewards.pop(index)

            if len(self.states) < batch_size:
                break
                
        self.states = []
        self.move_probs = []
        self.rewards = []
        
    @canLog(log_file = 'testNewNetwork.txt')
    def testNewNetwork(self, num_trials=25, against_random=False, against_simple=False):
        """ Test the trained network against an old version of the network
            or against a bot playing random moves.
        """
        new_network_score = 0
        if not against_random:
            old_network = network(self.parameters['network'], load_old=True)
        
        for trial in range(num_trials):
            if not against_random and not against_simple:
                self.log('-'*20)
                self.log('Playing trial {}'.format(trial))
            new_game = self.game_framework()
            
            old_network_color = random.choice([1, -1])
            new_network_color = -old_network_color

            if against_simple:
                simple_parameters = deepcopy(self.parameters)
                simple_parameters['mcts']['playouts'] = 1
            
            current_player = 1
            while True:
                if current_player == old_network_color:
                    if against_random:
                        move = random.choice(new_game.getLegalMoves())
                    elif against_simple:
                        tree_search = mcts(new_game, self.network, simple_parameters['mcts'], train=False)
                        move, _ = tree_search.getBestMove()
                    else:
                        tree_search = mcts(new_game, old_network, self.parameters['mcts'], train=False)
                        move, _ = tree_search.getBestMove()
                    new_game.move(move)
                else:
                    tree_search = mcts(new_game, self.network, self.parameters['mcts'], train=False)
                    move, move_probs = tree_search.getBestMove()
                    self.__logMove(new_game, move, move_probs)
                    new_game.move(move)
                
                if new_game.isGameOver():
                    break
                    
                current_player *= -1
                
            result = new_game.getResult()
            new_network_score += 1 if result == new_network_color else (-1 if result == old_network_color else 0)
            
        if abs(new_network_score) == num_trials:
            self.network.loadModel()
            return 0
        
        if new_network_score > num_trials*0.05:
            self.network.saveModel()

        if not against_random:
            old_network.sess.close()
            del old_network
        
        return new_network_score


    def __logMove(self, board, move, probabilities):
        self.log('\nState')
        self.log('{}'.format(str(board)))
        m = np.zeros((3,3))
        m[move] = 1.0
        self.log(format2DArray(probabilities.reshape((3,3)).transpose()))
        self.log(format2DArray(m))
        return

    

     
