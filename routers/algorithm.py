import pandas as pd
import numpy as np
import routingpy as rp
from python_tsp.exact import solve_tsp_dynamic_programming
import os
from fastapi import status, APIRouter, HTTPException
from models import supabase
from shapely import wkb

router = APIRouter(prefix="/algorithm", tags=["Algorithm"])

graphhopper_api_key = os.environ.get("GRAPHOPPER_API_KEY", None)

client_graphhopper = rp.Graphhopper(api_key=graphhopper_api_key)


# TODO does not depend on a user
@router.get("/tsp")
def tsp_algorithm(bus_id: int = 0):
    # Prepare data
    response = supabase\
        .table("bus_stop_mappings")\
        .select("*")\
        .eq("bus_id", bus_id)\
        .execute()
    bus_stop_data = response.data
    if not bus_stop_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specified bus line doesn't exist",
        )
    bus_stop_ids = [item['stop_id'] for item in bus_stop_data]
    all_stops = []
    for stop_id in bus_stop_ids:
        stop_response = supabase\
            .table("stops")\
            .select("*")\
            .eq("is_active", True)\
            .eq("stop_id", stop_id)\
            .execute()
        all_stops.extend(stop_response.data)
    df = pd.DataFrame(
        [
            {
                'long': wkb.loads(loc['location'], hex=True).x,
                'lat': wkb.loads(loc['location'], hex=True).y
            }
            for loc in all_stops
        ]
    )
    df = df.astype(float)
    df = df.values

    try:
        durations = get_time_matrix(df)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Couldn't calculate route: {e}",
        )
    # print(durations)
    sym_matrix = symmetricize(durations)
    points = solve_tcp(sym_matrix)
    sorted_stops = [all_stops[i] for i in points]
    # print(sorted_stops)
    return {"stops": sorted_stops}


# def prepare_data(points):
#     df = pd.DataFrame(points)
#     df = df['points'].apply(pd.Series)
#     df[['id', 'name', 'lat', 'long']] = df\
#         .apply(
#             lambda row: pd.Series({'id': row['id'], 'name': row['name'], 'lat': row['lat'], 'long': row['long']}),
#             axis=1
#         )
#     return df

# def get_coordinates(df):
#     df['long'], df['lat'] = zip(*df['location'].apply(lambda loc: (loc.longitude, loc.latitude)))
#     coordinates = df[['long', 'lat']].values
#     return coordinates


def get_time_matrix(coordinates):
    # TODO check if bus is available
    matrix = client_graphhopper.matrix(locations=coordinates, profile='car')
    durations = np.matrix(matrix.durations)
    return durations


def symmetricize(m, high_int=None):
    # if high_int not provided, make it equal to 10 times the max value:
    # this is a hack to make sure that the matrix solution ignores one part of the matrix
    if high_int is None:
        high_int = round(10 * m.max())
    m_bar = m.copy()
    np.fill_diagonal(m_bar, 0)
    u = np.matrix(np.ones(m.shape) * high_int)
    np.fill_diagonal(u, 0)
    m_symm_top = np.concatenate((u, np.transpose(m_bar)), axis=1)
    m_symm_bottom = np.concatenate((m_bar, u), axis=1)
    m_symm = np.concatenate((m_symm_top, m_symm_bottom), axis=0)
    # Concorde requires integer weights
    return m_symm.astype(int)


def solve_tcp(symmetric_matrix, comeback: bool = False):
    if not comeback:
        # doesn't come back to the start
        symmetric_matrix[:, 0] = 0
    permutation, _ = solve_tsp_dynamic_programming(symmetric_matrix)
    tour = permutation[::2]
    return tour
