"""
An Apache Airflow DAG, that fetches metal prices from ChartSeeker and
uploads it to the database.
"""

from datetime import datetime
import logging

# pylint: disable=import-error
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.hooks.http import HttpHook
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.exceptions import AirflowException

with DAG(
    dag_id="get_prices",
    description="Fetch metal prices and upload them to the database",
    start_date=datetime(2023, 10, 18),
    schedule_interval='@hourly',
    tags=['jakluz-de2.4'],
    catchup=False
) as dag:
    def _fetch_data(source_conn_id, tickers, **context) -> None:
        """
        Gets information about current metal prices and stores them in
        XCom.

        Arguments:
            source_conn_id - the connection id to the Chartseeker price
                         resource from Airflow Connections metastore,
                         passed as a keyword argument from the DAG
            tickers - list of symbols, that we want to fetch from
                    Chartseeker, in the exact order they are provided
                    by the source, passed as a keyword argument from
                    the DAG
            **context - DAG context

        Returns:
            nothing
        """
        logger = logging.getLogger(__name__)
        logger.info("About to fetch the data from service")
        hook = HttpHook(method='GET', http_conn_id=source_conn_id)

        try:
            response = hook.run(endpoint='/quotes/metals.txt')
            response.raise_for_status()
        except Exception as e:
            raise AirflowException(f"Fetching failed: {e}")
        logger.info("Fetching successful")

        data = response.json()
        prices = {symbol: data[i]['ask'] for i, symbol in enumerate(tickers)}
        logger.info(prices)

        context["task_instance"].xcom_push(key="prices", value=prices)

    fetch_data = PythonOperator(
        task_id = "fetch_data",
        python_callable = _fetch_data,
        op_kwargs = {"source_conn_id": 'chartseeker',
                     "tickers": ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"]}
    )

    def _upload_data(db_conn_id, **context) -> None:
        """
        Gets the pricing data from the 'fetch_data' task and uploads it
        into the database.

        Arguments:
            db_conn_id - the connection id to the PostgreSQL database
                         from Airflow Connections metastore, passed as
                         a keyword argument from the DAG
            **context - DAG context

        Returns:
            nothing
        """
        logger = logging.getLogger(__name__)

        prices = context["task_instance"].xcom_pull(task_ids="fetch_data", key="prices")
        data = ((datetime.now(), symbol, price) for symbol, price in prices.items())

        hook = PostgresHook(db_conn_id)
        logger.info("Starting DB upload")
        try:
            hook.insert_rows("prices", data)
        except Exception as e:
            raise AirflowException(f"Uploading failed: {e}")

        logger.info("Upload to the database successful")

    upload_data = PythonOperator(
        task_id = "upload_data_to_db",
        python_callable=_upload_data,
        op_kwargs = {"db_conn_id": 'pg-metal_prices'}
    )

    trigger_train_and_save_model = TriggerDagRunOperator(
       task_id="trigger_train_and_save_model",
       trigger_dag_id="train_and_save_model"
   )

    fetch_data >> upload_data >> trigger_train_and_save_model
