from __future__ import annotations

import pendulum

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

# A docstring to provide a description of the DAG
doc_md = """
### Example Test DAG

This DAG is a simple test to demonstrate the basic functionality of Airflow.

#### Purpose
- Runs three tasks in sequence.
- Shows how to pass data between tasks using the TaskFlow API.
- Includes a BashOperator to show a classic operator.

#### Tasks
1. **hello_airflow**: A BashOperator that prints the current date.
2. **extract**: A Python task that simulates extracting data.
3. **process**: A Python task that processes the data from the 'extract' task.
"""

@dag(
    dag_id="example_test_dag",
    start_date=pendulum.datetime(2025, 6, 10, tz="UTC"),
    schedule="@daily",
    catchup=False,
    doc_md=doc_md,
    tags=["example", "test"],
)
def example_test_dag():
    """
    A simple example DAG to test Airflow functionality.
    """

    # Task 1: A classic operator to run a shell command
    hello_airflow = BashOperator(
        task_id="hello_airflow",
        bash_command='echo "Hello from Airflow! The date is $(date)."'
    )

    @task
    def extract() -> dict:
        """
        Simulates extracting data by returning a dictionary.
        """
        print("Extracting data...")
        return {"name": "Gustavo", "city": "Curitiba"}

    @task
    def process(data: dict):
        """
        Simulates processing the data by printing it to the logs.
        """
        print(f"Processing data for user {data['name']} from {data['city']}.")
        # You could add more processing logic here
        return "Processed!"

    # --- Define Task Dependencies ---

    # The 'extract' and 'process' tasks are defined using the TaskFlow API.
    # To set their dependency, we simply call them one after the other.
    extracted_data = extract()
    processing_result = process(extracted_data)

    # The 'hello_airflow' task will run in parallel with the Python tasks
    # because no dependency has been defined for it.
    # To make it run first, you would do:
    # hello_airflow >> extracted_data


# Instantiate the DAG
example_test_dag()