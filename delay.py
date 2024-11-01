import os
import csv
import networkx as nx
import matplotlib.pyplot as plt

def read_csv(folder, file_name):
    file_path = os.path.join(folder, file_name)
    with open(file_path, mode='r') as file:
        reader = csv.reader(file)
        data = [row for row in reader]
    return data

def create_graph(topology):
    G = nx.DiGraph()
    for row in topology:
        if row[0] == 'LINK':
            _, link_id, src, src_port, dst, dst_port, domain = row
            G.add_edge(src, dst, link_id=link_id, src_port=src_port, dst_port=dst_port, domain=domain)
    return G

def visualize_graph(G):
    pos = nx.spring_layout(G, seed=42)  # Fixed seed for reproducible layout
    plt.figure(figsize=(12, 8))
    nx.draw(G, pos, with_labels=True, node_size=3000, node_color='lightblue', font_size=10, font_weight='bold')
    edge_labels = nx.get_edge_attributes(G, 'link_id')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
    plt.title("Network Topology")
    plt.show()

def create_lookup_table_from_file(folder, file_name):
    lookup_table = {}
    file_path = os.path.join(folder, file_name)
    with open(file_path, mode='r') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        for row in reader:
            src, dst, path = row
            lookup_table[(src, dst)] = path.split('->')
    return lookup_table

def calculate_token_bucket_params(streams):
    params = []
    for stream in streams[1:]:  # Skip header
        pcp, name, stream_type, src, dst, size, period, deadline = stream
        size = int(size)
        period = int(period)
        r = size / period
        b = size
        params.append((name, r, b, int(pcp), src, dst))
    return params

def calculate_delays(lookup_table, streams, token_bucket_params):
    delays = []
    for stream in streams[1:]:  # Skip header
        pcp, name_, stream_type, src, dst, size, period, deadline = stream
        path = lookup_table.get((src, dst))
        
        if path is None:
            print(f"No path between {src} and {dst}. Skipping this stream.")
            continue
        
        max_e2e_delay = 0
        
        for i in range(0, len(path) - 1, 3):
            src_node = path[i]
            link_id = path[i + 1]
            dst_node = path[i + 2]
            
            link_data = G.get_edge_data(src_node.split(':')[0], dst_node.split(':')[0])
            r_f, b_f, p_f, src_f, dst_f = next((r_, b_, p_, s_, d_) for name__, r_, b_, p_, s_, d_ in token_bucket_params if name__ == name_)
            d_TX_DQ = int(size) / r_f  # Transmission delay
            # Calculate interference from higher and same priority flows
            b_H = sum(b_ for name__, r_, b_, p_, s_, d_ in token_bucket_params if p_ > p_f and s_ == src_node and d_ == dst_node)
            r_H = sum(r_ for name__, r_, b_, p_, s_, d_ in token_bucket_params if p_ > p_f and s_ == src_node and d_ == dst_node)
            b_C = sum(b_ for name__, r_, b_, p_, s_, d_ in token_bucket_params if p_ == p_f and name__ != name_ and s_ == src_node and d_ == dst_node)
            r_C = sum(r_ for name__, r_, b_, p_, s_, d_ in token_bucket_params if p_ == p_f and name__ != name_ and s_ == src_node and d_ == dst_node)
            l_L = int(size)  # Assuming lower priority frame size is the same
            d_PQ_TX = (b_H + b_C + l_L) / (r_f - r_H)
            d_DQ_SO = d_TX_DQ  # Assuming shaping delay is equal to transmission delay for simplicity
            d_PQ_SO = d_PQ_TX + d_TX_DQ + d_DQ_SO  # Total per-hop delay
            max_e2e_delay += d_PQ_SO
        
        delays.append((name_, max_e2e_delay * 1e6 , deadline , '->'.join(path))) # Convert to microseconds
    
    return delays

def write_csv(file_path, data):
    with open(file_path, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['StreamName', 'MaxE2E(us)', 'Deadline(us)', 'Path'])
        writer.writerows(data)

# Main execution
folder = 'testData'


streams = read_csv(folder,'small-streams.v2.csv')
topology = read_csv(folder,'small-topology.v2.csv')
G = create_graph(topology)
visualize_graph(G)

lookup_table = create_lookup_table_from_file(folder,'shortest_paths.csv')
token_bucket_params = calculate_token_bucket_params(streams)
delays = calculate_delays(lookup_table , streams , token_bucket_params)
write_csv('solution.csv', delays)

print("Delays calculated and written to solution.csv")
