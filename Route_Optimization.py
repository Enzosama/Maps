import pandas as pd
import numpy as np
import folium
import osmnx as ox
import networkx as nx
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2

def load_destinations(file_path='Google_Map_Api/destination_vietnam.csv'):
    """Load destinations from a CSV file."""
    try:
        return pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Warning: Destinations file '{file_path}' not found.")
        return pd.DataFrame()

def predict_optimal_route(city, start_location, destinations_df):
    """Predict the optimal route for visiting multiple locations."""
    if destinations_df.empty:
        return None, None, None

    # Create map
    map = folium.Map(location=start_location, zoom_start=12)

    # Create road network graph
    G = ox.graph_from_point(start_location, dist=10000, network_type="drive")
    G = ox.add_edge_speeds(G, hwy_speeds={'residential': 30, 'secondary': 50, 'primary': 60})
    G = ox.add_edge_travel_times(G)

    # Find nearest nodes
    start_node = ox.distance.nearest_nodes(G, start_location[1], start_location[0]) 
    destinations_df["node"] = destinations_df.apply(
        lambda x: ox.distance.nearest_nodes(G, x.Longitude, x.Latitude), axis=1
    )
    lst_nodes = destinations_df["node"].tolist()

    # Ensure start node is included
    if start_node not in lst_nodes:
        lst_nodes.insert(0, start_node)

    # Create distance matrix
    distance_matrix = np.array([[
        nx.shortest_path_length(G, source=a, target=b, weight='travel_time')
        for b in lst_nodes
    ] for a in lst_nodes])

    # Set up routing problem
    manager = pywrapcp.RoutingIndexManager(len(lst_nodes), 1, 0)
    model = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        return int(distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)])

    transit_callback_index = model.RegisterTransitCallback(distance_callback)
    model.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Solve the problem
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    solution = model.SolveWithParameters(params)

    # Extract the route
    if solution: 
        index = model.Start(0)
        route = []
        route_distance = 0
        while not model.IsEnd(index):
            route.append(manager.IndexToNode(index))
            previous_index = index
            index = solution.Value(model.NextVar(index))
            route_distance += model.GetArcCostForVehicle(previous_index, index, 0)

        # Plot the route on the map
        route_coords = []
        for i in range(len(route) - 1):
            try:
                edge_data = ox.shortest_path(G, lst_nodes[route[i]], lst_nodes[route[i+1]], weight='travel_time')
                edge_geometry = ox.routing.route_to_gdf(G, edge_data, weight='travel_time')['geometry']
                route_coords.extend([list(geom.coords) for geom in edge_geometry])
            except Exception as e:
                print(f"Error getting route geometry: {e}")

        folium.PolyLine(route_coords, weight=2, color='red').add_to(map)

        for _, row in destinations_df.iterrows():
            folium.Marker([row['Latitude'], row['Longitude']], popup=row['Street Address']).add_to(map)

        return map, route_distance / 3600, route  # Convert seconds to hours
    else:
        return None, None, None

if __name__ == "__main__":
    # Test the function
    destinations = load_destinations()
    start_location = (destinations.iloc[0]['Latitude'], destinations.iloc[0]['Longitude'])
    map, distance, route = predict_optimal_route("Test City", start_location, destinations)
    if map:
        map.save("route_map.html")
        print(f"Total travel time: {distance:.2f} hours")
        print("Route:", route)
    else:
        print("Failed to generate route.")