"""Small geometry helpers for locating graph nodes relative to lat/lon points."""
from __future__ import annotations

import math

import networkx as nx

from app.services.geo_utils import haversine_distance_m


def nearest_node(graph: nx.Graph, latitude: float, longitude: float):
    """
    Return the id of the graph node closest to (latitude, longitude).

    Uses a simple linear scan with haversine distance. This is adequate
    for the local, radius-bounded graphs this system works with (typically
    a few thousand nodes); a KD-tree/BallTree would be the natural upgrade
    for larger graphs (see README "Future improvements").
    """
    if graph.number_of_nodes() == 0:
        raise ValueError("Cannot find nearest node in an empty graph.")

    best_node = None
    best_dist = float("inf")
    for node_id, data in graph.nodes(data=True):
        d = haversine_distance_m(latitude, longitude, data["latitude"], data["longitude"])
        if d < best_dist:
            best_dist = d
            best_node = node_id
    return best_node


def destination_point(latitude: float, longitude: float, bearing_deg: float, distance_m: float):
    """
    Given a start point, bearing (degrees, 0=north/clockwise), and
    distance in meters, compute the destination lat/lon using the
    standard spherical "direct geodesic" formula. Used to seed candidate
    loop waypoints around a start point.
    """
    earth_radius_m = 6371000.0
    delta = distance_m / earth_radius_m
    theta = math.radians(bearing_deg)

    phi1 = math.radians(latitude)
    lambda1 = math.radians(longitude)

    phi2 = math.asin(
        math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )

    return math.degrees(phi2), math.degrees(lambda2)
