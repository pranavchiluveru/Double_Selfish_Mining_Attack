import networkx as nx 
import transaction
import numpy as np
import random, time, threading
import numpy.random as nprandom
from block import Block
import events
from priority_queue import PriorityQueue
class Node:
    def __init__(self, node_id, coins ,hashing_power, is_slow, is_slow_cpu, exp_dist_mean, event_queue, genesis_block):
        # Data members
        self.node_id = node_id
        self.coins = coins
        self.is_slow = is_slow
        self.is_slow_cpu= is_slow_cpu
        self.hashing_power = hashing_power
        self.exp_dist_mean = exp_dist_mean 
        self.running = True
        self.neighbours = []    #list of nodes neighbours
        self.transaction_queue = []
        self.blocks = {     #dictionary of all blocks node has seen
            0: genesis_block
        }
        self.event_queue = event_queue 
        # self.time_of_block_arrival_list = []
        self.receivedStamps=[]
        self.prev_block_id = 0 
        self.first_block_time_stamp = 0
        self.last_block_time_stamp = 0
        self.block_queue = PriorityQueue()
        self.forked_blocks = []

    def __str__(self):
        return f"Node ID: {self.node_id}\nHashing Power: {self.hashing_power}\nIs Slow: {self.is_slow}\nIs slow CPU: {self.is_slow_cpu}\nCoins: {self.coins}\nNeighbours: {self.neighbours}\nAll Nodes: {self.all_nodes}\n"

    def generate_transaction(self):

        # Sample a transaction amount and a receiver uniformly at random
        transaction_amount = random.uniform(1, self.coins)  # Adjust the range as needed
        nodelistwithoutme = list(set(self.all_nodes.keys()) - set([self.node_id]))
        receiver_id = random.choice(nodelistwithoutme)  # Adjust the range as needed

        # adding and removing coins from ourselves and the receiver
        self.coins = self.coins - transaction_amount
        # print(f"all nodes: {self.all_nodes}")
        
        # Create the transaction and add it to the transaction queue
        new_transaction = transaction.Transaction(
            transaction_id = str(int(time.time()))+str(self.node_id),
            coins=transaction_amount,
            sender_id=self.node_id,
            receiver_id=receiver_id,
            timestamp = int(time.time())    
        )

        self.transaction_queue.append(new_transaction)

        # Schedule a TxnReceived event at each peer/neighbour, at the current time + network delay
        for neighbour in self.neighbours:
            delay = self.get_latency("transaction", neighbour.is_slow_cpu, neighbour.node_id)
            scheduled_timestamp = time.time() + delay  # Adjust the range as needed
            event = events.TxnReceived(
                event_created_by=self.node_id,
                node=neighbour,
                node_id=neighbour.node_id,
                timestamp=scheduled_timestamp,
                transaction=new_transaction
            )
            self.event_queue.push(event, event.timestamp)

        # print(f"Txn generated by= {self.node_id}")
        with open('file.txt', 'a') as file:
            file.write("Txn: "+str(new_transaction.transaction_id)+" generated by= "+str(self.node_id)+" at time: "+str(new_transaction.timestamp)+" \n")


    def receive_transaction(self, transaction, event_created_by):
        # Check if the transaction has already been received
        with open('file.txt', 'a') as file:
            file.write("Txn: "+str(transaction.transaction_id)+" recieved by= "+str(self.node_id)+" at time: "+str(time.time())+" \n")

        if transaction.transaction_id not in [txn.transaction_id for txn in self.transaction_queue]:
            # Add the transaction to the received transactions
            self.transaction_queue.append(transaction)
            if transaction.receiver_id==self.node_id:
                # Schedule a TxnReceived event at each neighbour with a randomly sampled delay
                self.coins = self.coins + transaction.coins
            for neighbour in self.neighbours:
                if (neighbour.node_id != event_created_by):
                    delay = self.get_latency("transaction", neighbour.is_slow_cpu, neighbour.node_id)
                    scheduled_timestamp = time.time() + delay  # Adjust the range as needed
                    event = events.TxnReceived(
                        event_created_by=self.node_id,
                        node=neighbour,
                        node_id=neighbour.node_id,
                        timestamp=scheduled_timestamp,
                        transaction=transaction
                    )
                    self.event_queue.push(event, event.timestamp)

        
    
    def generate_block(self):
        self.transaction_queue.sort()


        transactions_in_block = [] 
        spent_transaction = self.get_spent_transactions() 
        #print(f"{type(spent_transaction)}")

        unspent_transactions = list(set(self.transaction_queue) - spent_transaction)
        for i in range(min(1000, len(unspent_transactions))):
            transactions_in_block.append(unspent_transactions[i])
        prev_longest_chain = self.get_longest_chain()
        mining_time = self.get_mining_time(prev_longest_chain) 
        print(f'First block time stamp: {self.first_block_time_stamp}\nLast block time stamp: {self.last_block_time_stamp}')
        print(f"mining_time: {mining_time}")
        # Create the coinbase transaction and add it to the transaction queue
        coinbase_transaction = transaction.Transaction(
            transaction_id=str(int(time.time()))+str(self.node_id),
            coins=50,
            sender_id=0,
            receiver_id=self.node_id,
            timestamp = time.time()
        )
        transactions_in_block.insert(0, coinbase_transaction)
        block = Block(
                block_id = str(int(time.time()))+str(self.node_id),
                created_by = self.node_id,
                mining_time = mining_time,
                prev_block_id = self.prev_block_id,
                transactions = transactions_in_block,
                length_of_chain = len(prev_longest_chain)+1,
                timestamp = time.time()
            )
        
        current_time = time.time()
        
        event  = events.BlockMined(self.node_id, self, self.node_id, current_time+mining_time, block)
        self.event_queue.push(event, event.timestamp)

        with open('file.txt', 'a') as file:
            file.write("Block: "+str(block.block_id)+" generated by= "+str(self.node_id)+" at time: "+str(time.time())+" \n")


    def mined_block(self, block):
        with open('file.txt', 'a') as file:
            file.write("Block: "+str(block.block_id)+" mined by= "+str(self.node_id)+" at time: "+str(time.time())+" \n")
        prev_longest_chain = len(self.blocks[self.prev_block_id])
        curr_longest_chain = len(block) 
        if(curr_longest_chain == prev_longest_chain + 1):
            self.blocks[block.block_id] = block
            self.prev_block_id = block.block_id 
            for neighbour in self.neighbours:
                delay = self.get_latency("block", neighbour.is_slow_cpu, neighbour.node_id)
                scheduled_timestamp = time.time() + delay  # Adjust the range as needed
                event = events.BlockReceive(
                    event_created_by=self.node_id,
                    node=neighbour,
                    node_id=neighbour.node_id,
                    timestamp=scheduled_timestamp,
                    block = block
                )
                self.event_queue.push(event, event.timestamp) 
                print(event)
        current_time = time.time()
        event  = events.BlockGenerate(self.node_id, self, self.node_id, current_time)
        self.event_queue.push(event, event.timestamp) 

    def receive_block(self, block, event_created_by):
        with open('file.txt', 'a') as file:
            file.write("Block: "+str(block.block_id)+" recieved by= "+str(self.node_id)+" at time: "+str(time.time())+" block_queue_size \n")
        print(f'Node {self.node_id} received Block: {block.block_id} mined by: {block.created_by} the current logest chain: {len(self.blocks[self.prev_block_id])}')
        
        if(self.prev_block_id == 0):
            # The chain is empty now the received block is first block to get added into the blockchain
            self.first_block_time_stamp = time.time() # Record the time at which first block is received
        self.last_block_time_stamp = time.time() # Record the time at which last block is received 
        
        self.block_queue.push(block, block.timestamp)
        prev_chain_len = len(self.blocks[self.prev_block_id])  # Chain length before adding block
        outstanding_block_list = []
        while not self.block_queue.is_empty() and self.block_queue.peek().prev_block_id in self.blocks.keys():
            # The block at the top of queue will get added to chain
            top_block = self.block_queue.pop()
            print(f'At node {self.node_id}, Block at the top of block queue is {top_block.block_id}')
            print(f'Block prev_block_id is {top_block.prev_block_id}, lenght of block {len(top_block)}, length before adding the block{len(top_block)}')
            # Check if the top_block is valid or not 
            if not self.is_valid(top_block):
                continue
            print(f"Bock {top_block.block_id} is valid block")
            
            print(f'Top block {top_block.block_id}, prev_block at node {self.node_id} is {self.prev_block_id}')
            if(top_block.prev_block_id == self.prev_block_id):
                # This means that the block will simply extend the current blockchain
                self.blocks[top_block.block_id] = top_block
                self.prev_block_id = top_block.block_id

            elif top_block.prev_block_id in self.blocks.keys():
                # This means that there is fork in the blokchain

                self.blocks[top_block.block_id] = top_block # First add block into the chain
                top_block_len = len(top_block) # Length of chain containing top_block (Forked chain)
                prev_block_len = len(self.blocks[self.prev_block_id]) # Length of chain where the node is pointing  

                if(top_block_len == prev_block_len):
                    pass
                elif(top_block_len < prev_block_len):
                    # Orphan the chain containing top_block 
                    pass
                elif(top_block_len > prev_block_len):
                    # Orphan the chain containing prev_block
                    self.prev_block_id = top_block.block_id 
            else:
                outstanding_block_list.append(top_block)
        for b in outstanding_block_list:
            self.block_queue.push(b)
        curr_chain_len = len(self.blocks[self.prev_block_id]) # Chain length after adding the block
        # Wait for the 6 confirmations before addign the mining reward to current coins
        if(curr_chain_len > prev_chain_len and curr_chain_len > 7) :
            curr_block_id = self.prev_block_id
            for i in range(6):
                curr_block_id = self.blocks[curr_block_id].prev_block_id
            if self.blocks[curr_block_id] == self.node_id:
                self.coins += 50

        # Now broadcast the received block to neighbours
        print(f"sending block to the neighbours")
        for neighbour in self.neighbours:
            if(neighbour.node_id != event_created_by):
                delay = self.get_latency("block", neighbour.is_slow_cpu, neighbour.node_id)
                scheduled_timestamp = time.time() + delay  # Adjust the range as needed
                event = events.BlockReceive(
                    event_created_by=self.node_id,
                    node=neighbour,
                    node_id=neighbour.node_id,
                    timestamp=scheduled_timestamp,
                    block = block
                )
                self.event_queue.push(event, event.timestamp)
                print(event)
        

    def get_spent_transactions(self):
        curr_node = self.prev_block_id
        spent_transaction = set()
        while curr_node != 0:
            spent_transaction.update(self.blocks[curr_node].transactions)
            curr_node = self.blocks[curr_node].prev_block_id 
            # curr_node
        return spent_transaction

    def get_mining_time(self, prev_longest_chain):
        avg_interarrival_time = (self.last_block_time_stamp - self.first_block_time_stamp)/len(prev_longest_chain)
        if(avg_interarrival_time == 0):
            avg_interarrival_time = 10
        hashing_power = 1 if (self.is_slow_cpu) else  0.1
        mining_time = nprandom.exponential(avg_interarrival_time/hashing_power)
        return mining_time
    
    def get_longest_chain(self):
        chain = []

        # Start with the genesis block
        longest_block = self.blocks[0]

        # Find the block ending with the longest chain
        for block in self.blocks.values():
            # Use block length and creation time to break ties in case of equal length
            if len(block) > len(longest_block) or (
            len(block) == len(longest_block) and block.timestamp < longest_block.timestamp):
                longest_block = block

        # Now find all the blocks in this chain
        current_block = longest_block

        # Do-While Loop!
        while True:
            chain.append(current_block)

            # Chain ends at Genesis block which has id 0
            if current_block.block_id == 0:
                break

            # Move backwards
            current_block = self.blocks[current_block.prev_block_id]

        return chain

    # Method to set the neighbours of current node
    def add_neighbours(self, neighbours):
        self.neighbours = neighbours 

    # Function to check if block is valid or not
    def is_valid(self, block):
        transaction = block.transactions
        for t in transaction:
            if t.coins < 0:
                return False
        return True
    
    # Method to save all node_ids in the blockchain network into the current node
    def add_allNodes(self, all_nodes):
        self.all_nodes = all_nodes
    
    # Method to get message latency
    def get_latency(self, message_type, is_receiver_slow, neighbour_id):
        latency = 0
        message_size = 0
        if(message_type == 'transaction'):
            message_size += 8*10**3
        elif(message_type == 'block'):
            message_size += 8*10**6
        
        link_speed = 0
        if not self.is_slow and not is_receiver_slow:
            link_speed = 100*10**8
        else:
            link_speed = 5*10**8
        
        # Transmission delay
        latency += message_size/link_speed

        # Queing delay
        latency += nprandom.exponential(96*1e3/link_speed)

        # Propagation delay
        latency += self.all_nodes[neighbour_id]

        return latency





