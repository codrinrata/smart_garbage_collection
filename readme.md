# Smart Garbage Collection

This presentation breaks down the Python code for our agent-based model of a garbage collection system, built using the Mesa framework.


## Agents

### 1. BuildingAgent

Role: Represents a building that generates trash.

Key Properties:

- trash_level: How much trash it currently holds.
- capacity: The maximum trash it can hold.
- trash_generation_rate: How much trash it produces each step.
- pickup_requested: A boolean flag (True/False) that it sets when it's nearly full.

Core Behavior (step method):

- It generates a bit of trash.
- It checks if its trash_level is over 80% of its capacity.
- If it is, it raises its hand by setting pickup_requested to True, signaling to the trucks that it needs service.

### 2. TruckAgent

Role: The active agent. It collects trash from buildings and transports it to the disposal site.

Key Properties:

- current_load & capacity: How much trash it's carrying and the max it can hold.
- state: This is crucial. It's a "state machine" that controls the truck's behavior. The states are:
    - patrolling: Looking for a building that needs pickup.
    - collecting: Moving towards a specific target building.
    - returning: Full of trash and heading to the disposal site.
    - target: The specific BuildingAgent it is currently moving towards.

Core Behavior (step method):

- Based on its current state, it performs an action (patrol, collect, or return). This is a clean way to manage complex behavior.
- Movement (_move_towards): Has built-in obstacle avoidance. If its direct path is blocked by another truck, it will try a secondary move to get around it, preventing gridlock.

### 3. DisposalSiteAgent

Role: A passive agent that acts as the final drop-off point for all trash.

Core Behavior: It does nothing on its own. It simply has a receive_trash method that trucks can call to unload their cargo.

## The Model

The GarbageCollectionModel class manages the entire simulation.

### Responsibilities:

- Sets up the world: It creates the MultiGrid—the 2D space where agents live.
- Manages Time: It uses a RandomActivation scheduler. This means in each "step" of the simulation, it activates every agent one by one in a random order.
- Creates the Agents: It populates the grid with the specified number of buildings and trucks.
- Collects Data: It uses a DataCollector to record key metrics at every step (e.g., total trash collected, number of buildings waiting). This data is what powers the charts in our visualization.

## Visualization

This is how Mesa's features are used to see the garbage colection in action, rather than just printing text.

**ModularServer**: This is the web server provided by Mesa that runs the simulation and serves the interactive webpage to our browser.

**agent_portrayal function**:  This is the "artist." It's a function that tells the server how to draw each agent on the grid. We use it to set the shape, size, color, and even text for each agent type, and we can change these dynamically (e.g., a building's color changes as its trash level increases).

**CanvasGrid**: The main grid visualization module.

**ChartModule**: Creates the live-updating line graphs from the data we're collecting.

**Slider**: Adds the sliders to the webpage, allowing us to easily change model parameters like the number of trucks and buildings before running a new simulation.

## How to run
1. Install required packages
```
pip install required.txt
```
2. Run the code
```
python garbageCollector.py
```
3. Navigate to http://127.0.0.1:8521 on a browser for visualization

