import pandas as pd
from supabase import create_client, Client
import requests
import numpy as np
import routingpy as rp
from python_tsp.exact import solve_tsp_dynamic_programming
import os

graphhopper_api_key = os.environ.get("GRAPHOPPER_API_KEY", None)

#INPUT: points = requests.get('http://localhost:8000/points_sorted?lat=0&long=0&token=testuser').json()
def prepare_data(points):
    df = pd.DataFrame(points)
    df = df['points'].apply(pd.Series)
    df[['id', 'name', 'lat', 'long']] = df.apply(lambda row: pd.Series({'id': row['id'], 'name': row['name'], 'lat': row['lat'], 'long': row['long']}), axis=1)
    return df

def get_coordinates(df):
    coordinates = df[['long', 'lat']].values
    return coordinates

def get_time_matrix(coordinates):
    api = rp.Graphhopper(api_key=graphhopper_api_key)
    matrix = api.matrix(locations=coordinates, profile='car') #TODO check if bus is available
    durations = np.matrix(matrix.durations)
    return durations

def symmetricize(m, high_int=None):
    # if high_int not provided, make it equal to 10 times the max value:
    # this is a hack to make sure that the matrix solution ignores one part of the matrix
    if high_int is None:
        high_int = round(10*m.max())
    m_bar = m.copy()
    np.fill_diagonal(m_bar, 0)
    u = np.matrix(np.ones(m.shape) * high_int)
    np.fill_diagonal(u, 0)
    m_symm_top = np.concatenate((u, np.transpose(m_bar)), axis=1)
    m_symm_bottom = np.concatenate((m_bar, u), axis=1)
    m_symm = np.concatenate((m_symm_top, m_symm_bottom), axis=0)
    return m_symm.astype(int) # Concorde requires integer weights


def solve_tcp(symmetric_matrix, comeback: bool = False):
    if not comeback:
        symmetric_matrix[:, 0] = 0 #doesn't come back to the start
    permutation, distance = solve_tsp_dynamic_programming(symmetric_matrix)
    tour = permutation[::2]
    return tour, distance

