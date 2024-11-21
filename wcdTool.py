
import networkx as nx
import csv
import argparse


class Graph:
    def __init__(self):
        # Initialize an empty NetworkX graph
        self.G = nx.Graph()
        self.stream_paths = {}  # Dictionary to store paths for each stream
        # Dictionary to store queue assignments for each output port
        self.queue_assignments = {}

    def load_from_csv(self, topology_file):
        """
        Loads a topology from a CSV file and populates the graph with nodes and edges.

        Args:
            topology_file (str): Path to the topology CSV file.
        """
        devices = []
        links = []

        # Use the csv module to read the file
        with open(topology_file, 'r') as file:
            reader = csv.reader(file)
            for fields in reader:
                if fields[0].lower() == 'es' or fields[0].lower() == 'sw':  # Device entry (SW or ES)
                    devices.append(fields)
                elif fields[0].lower() == 'link':  # Link entry
                    links.append(fields)

        # Add nodes (SW: Switch, ES: End System)
        for device in devices:
            device_type = device[0].strip()
            device_name = device[1].strip()
            self.G.add_node(device_name, type=device_type)

        # Add edges (LINK)
        for link in links:
            link_id = link[1].strip()
            source_device = link[2].strip()
            source_port = int(link[3].strip())
            destination_device = link[4].strip()
            destination_port = int(link[5].strip())

            # Add the edge (link) between source and destination devices, preserving direction information
            self.G.add_edge(
                source_device, destination_device, link_id=link_id,
                source_port=source_port, destination_port=destination_port,
                source_device=source_device, destination_device=destination_device
            )

    def load_streams(self, streams_file):
        """
        Loads stream information from a CSV file.

        Args:
            streams_file (str): Path to the streams CSV file.
        """
        streams = []
        with open(streams_file, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                streams.append({
                    'pcp': int(row[0]),
                    'name': row[1].strip(),
                    'type': row[2].strip(),
                    'source': row[3].strip(),
                    'destination': row[4].strip(),
                    'size': int(row[5])*8,
                    'period': float(row[6]),
                    'deadline': float(row[7])
                })
        self.streams = streams

        # debug print
        # for stream in self.streams:
        #     print(stream)

    def find_shortest_path(self, node_a, node_b):
        """
        Finds the shortest path between two nodes using Dijkstra's algorithm.

        Args:
            node_a (str): The source node.
            node_b (str): The destination node.

        Returns:
            path (list): The shortest path from node_a to node_b as a list of nodes.
        """
        try:
            # Verify that nodes exist in the graph
            if node_a not in self.G or node_b not in self.G:
                print(
                    f"One or both of the nodes ({node_a}, {node_b}) are not in the graph.")
                return None

            # Use Dijkstra's algorithm to find the shortest path without weights
            path = nx.shortest_path(self.G, source=node_a, target=node_b)
            return path
        except nx.NetworkXNoPath:
            print(f"No path exists between {node_a} and {node_b}.")
            return None
        except nx.NodeNotFound:
            print(
                f"One or both of the nodes ({node_a}, {node_b}) are not in the graph.")
            return None

    def calculate_all_paths(self):
        """
        Calculates and stores the shortest paths for all streams, adjusting for the direction of traversal.
        """
        for stream in self.streams:
            source = stream['source']
            destination = stream['destination']
            path = self.find_shortest_path(source, destination)
            if path:
                annotated_path = []
                for i in range(len(path) - 1):
                    current_node = path[i]
                    next_node = path[i + 1]

                    # Get edge data between current node and next node
                    edge_data = self.G.get_edge_data(current_node, next_node)
                    link_id = edge_data['link_id']

                    # Determine direction of traversal and select appropriate ports
                    if current_node == edge_data['source_device']:
                        source_port = edge_data['source_port']
                        destination_port = edge_data['destination_port']
                    else:
                        # If reversed, swap ports
                        source_port = edge_data['destination_port']
                        destination_port = edge_data['source_port']

                    # Annotate the current node details for the path
                    annotated_path.append(
                        f"{current_node}:{link_id}:{source_port}")

                # Append final destination node without outgoing link data
                annotated_path.append(f"{destination}")

                # Store annotated path in `stream_paths` dictionary
                self.stream_paths[stream['name']] = '->'.join(annotated_path)

                # Debug output
                # print(f"{stream['name']} from {source} to {destination}: {self.stream_paths[stream['name']]}")
            else:
                print(
                    f"No path found for Stream {stream['name']} from {source} to {destination}")

    def assign_queues(self):
        """
        Assigns shaped queues for each combination of priority level and upstream source for every output port.
        """
        for stream_name, path in self.stream_paths.items():
            stream = next(s for s in self.streams if s['name'] == stream_name)
            pcp = stream['pcp']
            path_nodes = path.split('->')
            for i in range(len(path_nodes) - 1):
                current_node = path_nodes[i].split(':')[0]
                previous_node = path_nodes[i -
                                           1].split(':')[0] if i > 0 else 'N/A'
                next_node = path_nodes[i + 1].split(':')[0]

                # Get edge data between current and next node
                edge_data = self.G.get_edge_data(current_node, next_node)

                # Determine output port based on traversal direction
                if current_node == edge_data['source_device']:
                    output_port = edge_data['source_port']
                else:
                    output_port = edge_data['destination_port']

                # Create a queue assignment key for each (current_node, previous_node, output_port, pcp)
                key = (current_node, previous_node, output_port, pcp)

                if key not in self.queue_assignments:
                    self.queue_assignments[key] = []
                self.queue_assignments[key].append(stream_name)

    def compute_worst_case_delay(self, stream_name, verbose=False):
        """
        Computes the worst-case per-hop delay for a stream over its path.

        Args:
            stream_name (str): The name of the stream.

        Returns:
            float: The computed worst-case delay for the stream.
        """
        if stream_name not in self.stream_paths:
            print(f"No path found for stream {stream_name}.")
            return None

        header_size = 0  # Ethernet frame header size
        path = self.stream_paths[stream_name].split('->')
        stream = next(s for s in self.streams if s['name'] == stream_name)
        b = stream['size'] + header_size  # Include Ethernet frame overhead
        r = b / stream['period']
        l_min = b  # Minimum frame size
        r_link = 1000000000  # Assume 1 Gbps link rate for now
        total_delay = 0

        if verbose:
            print(
                f"\nCalculating delay for stream: {stream_name}, size: {b}, period: {stream['period']}, deadline: {stream['deadline']}, pcp: {stream['pcp']}")

        for i in range(len(path) - 1):
            current_node = path[i].split(':')[0]
            next_node = path[i + 1].split(':')[0]
            edge_data = self.G.get_edge_data(current_node, next_node)

            # Determine output port based on traversal direction
            if current_node == edge_data['source_device']:
                output_port = edge_data['source_port']
            else:
                output_port = edge_data['destination_port']

            # Gather all streams at this output port across priority levels
            all_interfering_streams = [
                s_name for k, streams in self.queue_assignments.items()
                if k[0] == current_node and k[2] == output_port for s_name in streams
            ]

            # Organize interfering streams by priority level relative to `stream['pcp']`
            higher_priority_streams = []
            same_priority_streams = []
            lower_priority_streams = []

            for s_name in all_interfering_streams:

                s_data = next(
                    (s for s in self.streams if s['name'] == s_name and s['name'] != stream_name), None)
                if s_data:
                    if s_data['pcp'] > stream['pcp']:
                        higher_priority_streams.append(s_name)
                    elif s_data['pcp'] == stream['pcp']:
                        same_priority_streams.append(s_name)
                    else:
                        lower_priority_streams.append(s_name)

            # Debug output for all interfering streams organized by priority
            if verbose:
                print(
                    f"  At hop {current_node} -> {next_node}, output port {output_port}, link_id {edge_data['link_id']}:")
                print("    Higher-priority streams:", higher_priority_streams)
                print("    Same-priority streams:", same_priority_streams)
                print("    Lower-priority streams:", lower_priority_streams)

            # Calculate r_H: Total rate of higher-priority streams
            r_H = sum(
                (s_data['size'] + header_size) / s_data['period']
                for s_name in higher_priority_streams
                for s_data in self.streams if s_data['name'] == s_name)

            # Calculate b_H once per hop as the total burst size of all higher-priority streams
            b_H = sum(
                (s_data['size'] + header_size) for s_name in higher_priority_streams
                for s_data in self.streams if s_data['name'] == s_name)

            # Calculate l_L once per hop as the maximum size of lower-priority streams
            l_L = max(
                [(s_data['size'] + header_size) for s_name in lower_priority_streams
                 for s_data in self.streams if s_data['name'] == s_name] or [0])

            # TODO
            #######################################################################################
            # I dont think this is the correct way to calculate b_C_j. Why would we sum the burst of all same-priority interfering streams to get the worst-case scenario?
            # Calculate b_C_j as the sum of burst of any same-priority interfering stream
            # b_C_j = sum(
            #     [(s_data['size'] + header_size) for s_name in same_priority_streams
            #      for s_data in self.streams if s_data['name'] == s_name])

            # Patrick solution
            temp_list = [(s_data['size'] + header_size) for s_name in same_priority_streams
                         for s_data in self.streams if s_data['name'] == s_name]
            # exclude min burst from temp_list
            if len(temp_list) > 1:
                temp_list.remove(min(temp_list))
            else:
                temp_list = [0]
            b_C_j = sum(temp_list)

            # I think is the correct way to calculate b_C_j. It selects the max burst of the same priority streams, thus ensuring the worst-case scenario. This is same as the eq 10 in the project description.
            # Calculate b_C_j as the max of burst of any same-priority interfering stream
            # b_C_j = max(
            #     [(s_data['size'] + header_size) for s_name in same_priority_streams
            #      for s_data in self.streams if s_data['name'] == s_name] or [0])
            #######################################################################################

            # Debug output for r_H, b_H, l_L and b_C_j
            if verbose:
                print(
                    f"    Calculated b_H = {b_H}, b_C_j = {b_C_j}, b = {b}, l_min = {l_min}, l_L = {l_L}, r = {r_link}, r_H = {r_H}")

            # Calculate the per-hop delay using the worst-case conditions at this hop
            try:
                per_hop_delay = (b_H + b_C_j + (b - l_min) +
                                 l_L) / (r_link - r_H) + (l_min / r_link)
            except:
                return None

            if verbose:
                print(
                    f"    Per-hop delay at {current_node} -> {next_node} for stream {stream_name}: {per_hop_delay}")

            total_delay += per_hop_delay

        if verbose:
            print(f"Total delay for stream {stream_name}: {total_delay}")
        # return f'{stream_name}, {round(total_delay*1e6,3)}, {stream["deadline"]}, {self.stream_paths[stream_name]}'
        return total_delay

    def compute_worst_case_delay_for_all_streams(self, topology_file, streams_file, output_file='output.csv', verbose=False):
        """
        Computes the worst-case per-hop delay for all streams over their respective paths.
        """
        # Build the graph
        self.load_from_csv(topology_file)

        # Load streams
        self.load_streams(streams_file)

        # calculate stream paths
        self.calculate_all_paths()

        # assign queues
        self.assign_queues()

        with open(output_file, 'w') as file:
            writer = csv.writer(file)
            writer.writerow(
                'StreamName, MaxE2E(us), Deadline(us), Path'.split(','))
            for stream_name in self.stream_paths.keys():
                wcd = self.compute_worst_case_delay(
                    stream_name, verbose=verbose)
                writer.writerow(
                    f'{stream_name}, {round(wcd*1e6,3)}, {self.streams[0]["deadline"]}, {self.stream_paths[stream_name]}'.split(','))


# Example usage
topology_file = 'topology.csv'  # Replace with your actual file path
streams_file = 'streams.csv'  # Replace with your actual file path

graph = Graph()
graph.compute_worst_case_delay_for_all_streams(
    topology_file=topology_file, streams_file=streams_file, output_file='output.csv', verbose=True)

if __name__ == '__main__':
    # use arogparse to get the file paths
    parser = argparse.ArgumentParser(
        description='Compute worst-case delay for all streams')
    parser.add_argument('--topology_file', '-tf', default='topology.scv',
                        type=str, help='Path to the topology CSV file')
    parser.add_argument('--streams_file', '-sf', default='streams.csv',
                        type=str, help='Path to the streams CSV file')
    args = parser.parse_args()

    # Example usage
    topology_file = 'topology.csv'  # Replace with your actual file path
    streams_file = 'streams.csv'  # Replace with your actual file path

    graph = Graph()
    graph.compute_worst_case_delay_for_all_streams(
        topology_file=args.topology_file, streams_file=args.streams_file, output_file='output.csv', verbose=True)
