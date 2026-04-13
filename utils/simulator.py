import pandas as pd

def run_simulation(agents, network):
    history = []
    logs = []
    
    timestamps = pd.date_range(start="2026-01-01", periods=144, freq="10min")
    for t in timestamps:

        total = 0
        
        for agent in agents:
            data= agent.generate(t)
            total += data["n_bytes"]
            if(agent.name != "Persona"):
                if data["state_changed"]:
                    logs.append({
                    "timestamp": t,
                    "agent": agent.name,
                    "event": data["state"]
                })
        net = network.evaluate(total)
        
        history.append({
            "time": t,
            "traffic": total/8e6,  
            "load": net["load"],
            "latency": net["latency"],
            "packet_loss": net["packet_loss"]
        })
    
    return pd.DataFrame(history), pd.DataFrame(logs)

def run_multiple_simulations(agents, network, runs=10):
    import pandas as pd
    
    all_histories = []
    all_logs = []
    
    for _ in range(runs):
        history_df, logs_df = run_simulation(agents, network)
        
        all_histories.append(history_df)
        all_logs.append(logs_df)
    
    combined_history = pd.concat(all_histories)
    avg_history = combined_history.groupby("time").mean().reset_index()
    
    combined_logs = pd.concat(all_logs).reset_index(drop=True)
    
    return avg_history, combined_logs