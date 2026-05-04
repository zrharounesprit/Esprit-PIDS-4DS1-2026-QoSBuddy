import pickle
import os

def load_correlation_matrix():
    path = os.path.join(os.path.dirname(__file__),
                        '..', 'artifacts', 'correlation_matrix.pkl')
    with open(path, 'rb') as f:
        return pickle.load(f)

def load_dependency_graph():
    path = os.path.join(os.path.dirname(__file__),
                        '..', 'artifacts', 'dependency_graph.pkl')
    with open(path, 'rb') as f:
        return pickle.load(f)

def get_strong_correlations(matrix, threshold=0.7):
    results = []
    cols = matrix.columns
    for i in range(len(cols)):
        for j in range(i+1, len(cols)):
            val = matrix.iloc[i, j]
            if abs(val) > threshold:
                direction = "also increases" if val > 0 else "decreases"
                strength = "strongly" if abs(val) > 0.9 else "moderately"
                results.append({
                    'kpi_1': cols[i],
                    'kpi_2': cols[j],
                    'correlation': round(val, 2),
                    'direction': direction,
                    'strength': strength,
                    'sentence': f"When {cols[i]} increases, "
                                f"{cols[j]} {direction} "
                                f"({strength}, r={round(val, 2)})"
                })
    return results