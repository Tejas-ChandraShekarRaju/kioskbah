from locust import HttpUser, task, between

class FloorPlanUser(HttpUser):
    wait_time = between(1, 2)  # simulate wait time between requests

    @task
    def show_featured_plans(self):
        self.client.get("/check_floor_plan_and_elevation?view=featured")
