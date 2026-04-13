import math
class Network:
    def __init__(self, capacity):
        self.capacity = capacity
    
    def evaluate(self, total_traffic):
        load = total_traffic / self.capacity
        base_latency = 10
        
        effective_load = min(load, 0.99) 
        latency = base_latency / (1 - effective_load)
        
        if load >= 1:
            latency += (load - 1) * 500 
        
        packet_loss = 1 / (1 + math.exp(-10 * (load - 1.1))) if load > 0.8 else 0

        return {
            "load": load,
            "latency": latency,
            "packet_loss": packet_loss
        }