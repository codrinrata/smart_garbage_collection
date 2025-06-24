import mesa
import numpy as np
from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector
from mesa.visualization.modules import CanvasGrid, ChartModule
from mesa.visualization.ModularVisualization import ModularServer
from enum import Enum

class AgentType(Enum):
    BUILDING = "building"
    TRUCK = "truck"
    DISPOSAL = "disposal"

class BuildingAgent(Agent):
    """Garbage Generator Agent - represents buildings that generate trash"""
    
    def __init__(self, unique_id, model, trash_generation_rate=1, capacity=10):
        super().__init__(unique_id, model)
        self.trash_level = 0
        self.capacity = capacity
        self.trash_generation_rate = trash_generation_rate
        self.pickup_requested = False
        self.total_trash_generated = 0
        self.pickup_wait_time = 0
        self.agent_type = AgentType.BUILDING
        
    def step(self):
        if self.trash_level < self.capacity:
            self.trash_level += self.trash_generation_rate
            self.total_trash_generated += self.trash_generation_rate
        
        # Garbage pickup threshold (80% capacity)
        if self.trash_level >= self.capacity * 0.8 and not self.pickup_requested:
            self.pickup_requested = True
            self.pickup_wait_time = 0
            
        if self.pickup_requested:
            self.pickup_wait_time += 1
            
    def collect_trash(self):
        """Called by truck to collect trash"""
        collected = self.trash_level
        self.trash_level = 0
        self.pickup_requested = False
        self.pickup_wait_time = 0
        return collected

class TruckAgent(Agent):
    """Garbage Collector Agent - collects trash and delivers to disposal site"""
    
    def __init__(self, unique_id, model, capacity=50, speed=1):
        super().__init__(unique_id, model)
        self.capacity = capacity
        self.current_load = 0
        self.speed = speed
        self.state = "patrolling"
        self.target = None
        self.total_collected = 0
        self.trips_made = 0
        self.distance_traveled = 0
        self.agent_type = AgentType.TRUCK
        
    def step(self):
        for _ in range(self.speed):
            if self.state == "patrolling":
                self._patrol()
            elif self.state == "collecting":
                self._collect()
            elif self.state == "returning":
                self._return_to_disposal()

    def _patrol(self):
        buildings_needing_pickup = []
        for agent in self.model.schedule.agents:
            if isinstance(agent, BuildingAgent) and agent.pickup_requested:
                is_targeted = False
                for truck in self.model.trucks:
                    if truck.target == agent:
                        is_targeted = True
                        break
                if not is_targeted:
                    buildings_needing_pickup.append(agent)
                
        if buildings_needing_pickup:
            closest_building = min(buildings_needing_pickup, 
                                 key=lambda b: self._distance_to(b.pos))
            self.target = closest_building
            self.state = "collecting"
        else:
            self._move_randomly()
            
    def _collect(self):
        if self.target is None or not self.target.pickup_requested:
            self.state = "patrolling"
            self.target = None
            return

        if self.pos != self.target.pos:
            self._move_towards(self.target.pos)
        else:
            collected = self.target.collect_trash()
            self.current_load += collected
            self.total_collected += collected
            self.target = None

            if self.current_load >= self.capacity:
                self.state = "returning"
            else:
                self.state = "patrolling"
                
    def _return_to_disposal(self):
        if not self.model.disposal_site:
            return
        
        disposal_pos = self.model.disposal_site.pos
        if self.pos != disposal_pos:
            self._move_towards(disposal_pos)
        else:
            self.model.disposal_site.receive_trash(self.current_load)
            self.current_load = 0
            self.trips_made += 1
            self.state = "patrolling"

    def _move_towards(self, target_pos):
        """Move towards target position, with simple obstacle avoidance."""
        x, y = self.pos
        dx = target_pos[0] - x
        dy = target_pos[1] - y

        if abs(dx) > abs(dy):
            if self._try_move((x + np.sign(dx), y), target_pos): return
            if self._try_move((x, y + np.sign(dy)), target_pos): return
        else:
            if self._try_move((x, y + np.sign(dy)), target_pos): return
            if self._try_move((x + np.sign(dx), y), target_pos): return

        self._move_randomly()

    def _try_move(self, new_pos, target_pos):
        """Attempts to move to a new position if it's not blocked by another truck."""
        if not self.model.grid.out_of_bounds(new_pos):
            is_occupied_by_truck = any(isinstance(agent, TruckAgent) for agent in self.model.grid.get_cell_list_contents([new_pos]))
            
            if not is_occupied_by_truck or new_pos == target_pos:
                self.model.grid.move_agent(self, new_pos)
                self.distance_traveled += 1
                return True
        return False
            
    def _move_randomly(self):
        """Random movement for patrolling, avoiding other trucks."""
        possible_steps = self.model.grid.get_neighborhood(
            self.pos, moore=True, include_center=False
        )
        valid_steps = []
        for pos in possible_steps:
            if not self.model.grid.out_of_bounds(pos):
                if not any(isinstance(agent, TruckAgent) for agent in self.model.grid.get_cell_list_contents([pos])):
                    valid_steps.append(pos)

        if valid_steps:
            new_position = self.random.choice(valid_steps)
            self.model.grid.move_agent(self, new_position)
            self.distance_traveled += 1
            
    def _distance_to(self, pos):
        """Calculate distance from agent's current pos to a target pos."""
        return abs(self.pos[0] - pos[0]) + abs(self.pos[1] - pos[1])

class DisposalSiteAgent(Agent):
    """Disposal Site Agent - receives trash from trucks"""
    
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.total_received = 0
        self.agent_type = AgentType.DISPOSAL
        
    def receive_trash(self, amount):
        """Receive trash from truck"""
        self.total_received += amount
        
    def step(self):
        pass

class GarbageCollectionModel(Model):
    """Main model for the garbage collection simulation"""
    
    def __init__(self, width=20, height=20, n_buildings=10, n_trucks=2):
        super().__init__()
        self.width = width
        self.height = height
        self.n_buildings = n_buildings
        self.n_trucks = n_trucks
        
        self.grid = MultiGrid(width, height, True)
        self.schedule = RandomActivation(self)
        
        self.trucks = []
        self.disposal_site = None
        
        self._create_buildings()
        self._create_trucks()
        self._create_disposal_site()
        
        self.datacollector = DataCollector(
            model_reporters={
                "Total Trash Generated": lambda m: sum(
                    agent.total_trash_generated for agent in m.schedule.agents 
                    if isinstance(agent, BuildingAgent)
                ),
                "Total Trash Collected": lambda m: sum(
                    agent.total_collected for agent in m.schedule.agents 
                    if isinstance(agent, TruckAgent)
                ),
                "Average Wait Time": lambda m: np.mean([
                    agent.pickup_wait_time for agent in m.schedule.agents 
                    if isinstance(agent, BuildingAgent) and agent.pickup_requested
                ]) if any(agent.pickup_requested for agent in m.schedule.agents 
                         if isinstance(agent, BuildingAgent)) else 0,
                "Buildings Needing Pickup": lambda m: sum(
                    1 for agent in m.schedule.agents 
                    if isinstance(agent, BuildingAgent) and agent.pickup_requested
                ),
            }
        )
        
        self.running = True
        self.datacollector.collect(self)
        
    def _create_buildings(self):
        for i in range(self.n_buildings):
            pos = self.grid.find_empty()
            if pos:
                trash_rate = self.random.uniform(0.5, 2.0)
                capacity = self.random.randint(8, 15)
                building = BuildingAgent(f"b_{i}", self, trash_rate, capacity)
                self.grid.place_agent(building, pos)
                self.schedule.add(building)
            
    def _create_trucks(self):
        for i in range(self.n_trucks):
            pos = self.grid.find_empty()
            if pos:
                capacity = self.random.randint(40, 60)
                speed = self.random.randint(1, 2)
                truck = TruckAgent(f"t_{i}", self, capacity, speed)
                self.grid.place_agent(truck, pos)
                self.schedule.add(truck)
                self.trucks.append(truck)
            
    def _create_disposal_site(self):
        self.disposal_site = DisposalSiteAgent("disposal", self)
        pos = (0, 0)
        if not self.grid.is_cell_empty(pos):
             for agent in self.grid.get_cell_list_contents([pos]):
                 self.grid.move_to_empty(agent)
        self.grid.place_agent(self.disposal_site, pos)
        self.schedule.add(self.disposal_site)
        
    def step(self):
        """Advance the model by one step"""
        self.schedule.step()
        self.datacollector.collect(self)

# --- MESA VISUALIZATION SETUP ---

def agent_portrayal(agent):
    """Defines how each agent is drawn in the visualization."""
    portrayal = {"Shape": "rect", "Filled": "true", "Layer": 0, "w": 1, "h": 1}

    if agent.agent_type == AgentType.BUILDING:
        portrayal["Shape"] = "rect"
        portrayal["w"] = 0.8
        portrayal["h"] = 0.8
        fill_ratio = min(agent.trash_level / agent.capacity, 1.0)
        if agent.pickup_requested:
            portrayal["Color"] = "#FFC0CB"
            portrayal["stroke_color"] = "#000000"
        else:
            red = int(255 * fill_ratio)
            green = int(255 * (1 - fill_ratio))
            portrayal["Color"] = f"rgb({red},{green},0)"
        
        portrayal["text"] = f"{agent.trash_level:.1f}"
        portrayal["text_color"] = "white"

    elif agent.agent_type == AgentType.TRUCK:
        portrayal["Shape"] = "circle"
        portrayal["r"] = 0.6
        portrayal["Layer"] = 1
        if agent.state == "returning":
            portrayal["Color"] = "orange"
        else:
            portrayal["Color"] = "blue"
        portrayal["text"] = f"{agent.current_load:.0f}"
        portrayal["text_color"] = "white"

    elif agent.agent_type == AgentType.DISPOSAL:
        portrayal["Shape"] = "rect"
        portrayal["w"] = 1
        portrayal["h"] = 1
        portrayal["Color"] = "black"
        portrayal["text"] = "D"
        portrayal["text_color"] = "white"
        
    return portrayal

GRID_WIDTH = 20
GRID_HEIGHT = 20

grid = CanvasGrid(agent_portrayal, GRID_WIDTH, GRID_HEIGHT, 600, 600)

chart_collection = ChartModule([
    {"Label": "Total Trash Generated", "Color": "Orange"},
    {"Label": "Total Trash Collected", "Color": "Green"}
], data_collector_name='datacollector')

chart_waiting = ChartModule([
    {"Label": "Buildings Needing Pickup", "Color": "Red"}
], data_collector_name='datacollector')

server = ModularServer(
    GarbageCollectionModel,
    [grid, chart_collection, chart_waiting],
    "Smart Garbage Collection - Codrin Rață",
    {
        "n_buildings": mesa.visualization.Slider("Number of Buildings", 10, 2, 50, 1),
        "n_trucks": mesa.visualization.Slider("Number of Trucks", 2, 1, 10, 1),
        "width": GRID_WIDTH,
        "height": GRID_HEIGHT,
    }
)

if __name__ == "__main__":
    server.port = 8521  # default port
    print(f"Starting server on http://127.0.0.1:{server.port}")
    server.launch()
