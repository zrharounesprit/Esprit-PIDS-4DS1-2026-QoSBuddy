import numpy as np
import pandas as pd

class SmartAgent:
    def __init__(self, profile, name="Agent"):
        self.name = name
        self.profile = profile
        if(self.profile["bytes"] is not None):
            self.q1 = self.profile["bytes"].quantile(0.25)
            self.q2 = self.profile["bytes"].quantile(0.50)
            self.q3 = self.profile["bytes"].quantile(0.75)
        else:
            self.q1 = 0
            self.q2 = 0
            self.q3 = 0
        self.last_state = None
    
    def infer_state(self, n_bytes):
        if n_bytes < self.q1:
            return "idle"
        elif n_bytes < self.q2:
            return "browsing"
        elif n_bytes < self.q3:
            return "gaming"
        else:
            return "streaming"
    
    def generate(self, timestamp):
        hour = timestamp.hour
        
        mean = self.profile["hourly_mean"].get(hour, self.profile["bytes_mean"])
        std = self.profile["hourly_std"].get(hour, self.profile["bytes_std"])
        
        

        n_bytes = max(np.random.normal(mean, std), 0)

        state = self.infer_state(n_bytes)
        
        if self.last_state is not None and np.random.rand() < 0.8:
            state = self.last_state

        state_changed = state != self.last_state

        self.last_state = state

        if np.random.rand() < 0.05:
            n_bytes *= 2
        n_bytes = max(n_bytes, 0)
        
        corr = self.profile["corr"]
        
        n_packets = n_bytes * corr.loc["n_bytes", "n_packets"]
        n_flows = n_bytes * corr.loc["n_bytes", "n_flows"]
        
        return {
            "n_bytes": n_bytes,
            "n_packets": n_packets,
            "n_flows": n_flows,
            "state": state,
            "state_changed": state_changed
        }


def extract_profile(df):
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df["hour"] = df["timestamp"].dt.hour
    df["dayofweek"] = df["timestamp"].dt.dayofweek
    return {
        "bytes":df["n_bytes"],
        "bytes_mean": df["n_bytes"].mean(),
        "bytes_std": df["n_bytes"].std(),
        "packets_mean": df["n_packets"].mean(),
        "flows_mean": df["n_flows"].mean(),
        "hourly_mean": df.groupby("hour")["n_bytes"].mean(),
        "hourly_std": df.groupby("hour")["n_bytes"].std(),
        "corr": df[["n_bytes", "n_packets", "n_flows"]].corr(),
        "type": classify_user(df)
        
    }

def classify_user(df):
    if df["n_bytes"].mean() > 1e6:
        return "streamer"
    elif df["n_packets"].std() > df["n_packets"].mean():
        return "gamer"
    return "normal"