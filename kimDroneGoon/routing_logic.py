from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_tsp(locations_gdf):
    # 1. Create Distance Matrix (scaled to integers)
    # OR-Tools requires integers; multiply floats by 100 to keep precision
    num_locations = len(locations_gdf)
    dist_matrix = []
    for i in range(num_locations):
        row = []
        for j in range(num_locations):
            if i == j:
                row.append(0)
            else:
                # Use GeoPandas distance (or Haversine if using lat/long)
                d = locations_gdf.iloc[i].geometry.distance(locations_gdf.iloc[j].geometry)
                row.append(int(d * 100)) 
        dist_matrix.append(row)

    # 2. Setup Routing Model
    manager = pywrapcp.RoutingIndexManager(num_locations, 1, 0) # 1 vehicle, starting at index 0
    routing = pywrapcp.RoutingModel(manager)

    # 3. Create Distance Callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return dist_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # 4. Set Search Strategy
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    # 5. Solve
    solution = routing.SolveWithParameters(search_parameters)

    # 6. Extract Route
    route = []
    if solution:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index)) # Return to start
    return route
