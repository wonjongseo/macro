class RoutePatrol:
    """사용자가 미리 정한 경로를 무한 반복한다."""
    def __init__(self, waypoints):
        """
        waypoints: list of dicts
            [{ "x":100, "y":120, "action":"move"   },
             { "x":300, "y":120, "action":"jump"   },
             { "x": 57, "y":140, "action":"ladder" }]
        """
        self.waypoints = waypoints
        self.index = 0

    def current_wp(self):
        return self.waypoints[self.index]

    def advance(self):
        self.index = (self.index + 1) % len(self.waypoints)
