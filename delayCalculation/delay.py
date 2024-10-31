import pandas as pd

# Load CSV files
streams_df = pd.read_csv('small-streams.v2.csv')
shortest_path_df = pd.read_csv('shortest_paths_between_ES.csv')

# Convert Size from bytes to bits and Period from microseconds to seconds
streams_df['Size (bits)'] = streams_df['Size'] * 8  # Convert bytes to bits
streams_df['Period (s)'] = streams_df['Period'] * 1e-6  # Convert microseconds to seconds

# Calculate burst size and committed transmission rate
streams_df['Burst Size (b)'] = streams_df['Size (bits)']  # Burst size in bits
streams_df['Committed Transmission Rate (r)'] = streams_df['Size (bits)'] / streams_df['Period (s)']  # r in bits per second

# Link rate
link_rate = 1_000_000_000  # 1 Gbps in bits per second

# Initialize results list
results = []

# Calculate maximum delays for each path
for _, path_row in shortest_path_df.iterrows():
    source = path_row['Source']
    destination = path_row['Destination']
    path = path_row['Path']
    
    # Count the number of switches in the path (hops)
    num_switches = path.count('sw')
    
    # Find relevant streams for this source and destination
    relevant_streams = streams_df[(streams_df['SourceNode'] == source) & 
                                   (streams_df['DestinationNode'] == destination)]
    
    for _, stream_row in relevant_streams.iterrows():
        pcp = stream_row['PCP']
        burst_size = stream_row['Burst Size (b)']  # Burst size in bits
        committed_rate = stream_row['Committed Transmission Rate (r)']  # Committed rate in bits per second
        
        # Set r_H based on PCP
        if pcp == 6:
            r_H = committed_rate  # For PCP 6, use committed rate
        elif pcp == 7:
            r_H = 0  # For PCP 7, set r_H to 0
        else:
            continue  # Skip other priorities if needed

        # Use a small epsilon to prevent division by zero
        epsilon = 1e-9
        
        # Burst interference (this can be adjusted based on your model)
        b_I = 0  # Set this to 0 as per your earlier note
        
        # Check for zero division
        if abs(committed_rate - r_H) > epsilon:
            # Delay calculation using the simplified formula
            max_delay = ((burst_size + b_I) / (committed_rate - r_H) + (link_rate / committed_rate)) * 1e6  # Convert to microseconds
        else:
            # Handle case where committed_rate is approximately equal to r_H
            max_delay = float('inf')  # or set to a high constant, or use an alternative formula
            
        # Extract flow number from StreamName
        flow_number = int(stream_row['StreamName'].split('_')[-1])  # Assuming format "Stream_X"
        
        # Store results
        results.append({
            'Source': source,
            'Destination': destination,
            'PCP': pcp,
            'Hops': num_switches,
            'MaxDelay (us)': max_delay,
            'FlowNumber': flow_number  # Adding flow number to results
        })

# Create a DataFrame for results
results_df = pd.DataFrame(results)

# Sort results by FlowNumber
results_df.sort_values(by='FlowNumber', inplace=True)

# Output results to CSV
results_df.to_csv('maximum_delays.csv', index=False)

print("Maximum delays have been calculated and saved to 'maximum_delays.csv'.")
