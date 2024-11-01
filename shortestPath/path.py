import csv
import networkx as nx
import matplotlib.pyplot as plt

#Algorithm for finding the shortest path currently with BFS

def parse_topology(filename):
    devices = parse_devices(filename)
    links = parse_links(filename)
    return devices, links

# Function to parse devices from the CSV file
def parse_devices(file_name):
    devices = {}

    with open(file_name, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip the header row
        for row in reader:
            if row[0] != 'LINK':  # Only process device rows
                device_type, device_name, ports = row[:3]
                devices[device_name] = {'type': device_type, 'ports': int(ports)}
    
    return devices

# Function to parse links from the CSV file
def parse_links(file_name):
    links = []

    with open(file_name, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip the header row
        for row in reader:
            if row[0] == 'LINK':  # Only process link rows
                try:
                    link_id = row[1]
                    src_device = row[2]
                    src_port = int(row[3])  # Ensure src_port is an integer
                    dst_device = row[4]
                    dst_port = int(row[5])  # Ensure dst_port is an integer
                    links.append((link_id, src_device, src_port, dst_device, dst_port))
                except IndexError:
                    print(f"Link row has missing values: {row}")
                except ValueError:
                    print(f"Invalid value in row: {row}")
    
    return links

def build_graph(devices, links):
    G = nx.Graph()
    for device_name in devices.keys():
        G.add_node(device_name)
    
    for link in links:
        if len(link) == 5:  # Check if link has exactly 5 values
            link_id, src_device, src_port, dest_device, dest_port = link
            G.add_edge(src_device, dest_device, link_id=link_id, src_port=src_port, dest_port=dest_port)
        else:
            print(f"Link has an unexpected number of values: {link}")
    
    return G

def visualize_graph(graph):
    pos = nx.spring_layout(graph)
    nx.draw(graph, pos, with_labels=True, node_color='lightblue', node_size=2000, font_size=10)
    edge_labels = nx.get_edge_attributes(graph, 'link_id')
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels)
    plt.show()

def find_shortest_paths_between_ES(graph, devices):
    es_devices = [name for name, info in devices.items() if info['type'] == 'ES']
    all_paths = []

    for source in es_devices:
        for target in es_devices:
            if source != target:
                # Find the shortest path between source and target
                path = nx.shortest_path(graph, source, target)
                formatted_path = []
                
                # Build the formatted path with link IDs and ports
                for i in range(len(path) - 1):
                    current_device = path[i]
                    next_device = path[i + 1]
                    edge_data = graph[current_device][next_device]
                    link_id = edge_data['link_id']
                    
                    # Append formatted string
                    if i == 0:  # First device
                        formatted_path.append(current_device)
                    formatted_path.append(f"{link_id}->{edge_data['src_port']}-{next_device}")
                
                # Create a tuple for the path
                path_tuple = (source, target, "->".join(formatted_path))
                all_paths.append(path_tuple)

    return all_paths

def main():
    devices, links = parse_topology('testData/'+'small-topology.v2.csv')
    
    graph = build_graph(devices, links)
    
    # Optionally visualize the graph
    visualize_graph(graph)

    # Find shortest paths between End Systems (ES)
    all_paths = find_shortest_paths_between_ES(graph, devices)

    # Write to CSV
    with open('testData/'+'shortest_paths.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Source', 'Destination', 'Path'])
        writer.writerows(all_paths)

if __name__ == "__main__":
    main()
