"""
An Apache Airflow DAG, that fetches metal prices from ChartSeeker and
uploads it to the database.
"""

from collections import defaultdict
from datetime import datetime
import logging
import pandas as pd

# pylint: disable=import-error
from airflow import DAG
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException

from model import Model

with DAG(
    dag_id="train_and_save_model",
    description="Gets the training data from the database and uses it"
                "to train the model, then saves it",
    start_date=datetime(2023, 10, 18),
    schedule_interval=None,
    tags=['jakluz-de2.4'],
    catchup=False
) as dag:

    def _get_training_data_from_db(db_conn_id, **context) -> None:
        """
        Fetches the training data from the database and stores it in
        XCom for later use.

        Arguments:
            db_conn_id - the connection id to the PostgreSQL database
                         from Airflow Connections metastore, passed as
                         a keyword argument from the DAG
            **context - DAG context

        Returns:
            nothing
        """
        logger = logging.getLogger(__name__)

        hook = PostgresHook(db_conn_id)
        logger.info("Fetching data from the database")
        try:
            data = hook.get_records("SELECT * FROM training_data;")
        except Exception as e:
            raise AirflowException(f"Fetching failed: {e}")

        logger.info("Fetching from the database successful")

        data_dict = defaultdict(list)

        #pylint: disable=not-an-iterable
        for ticker, price in data:
            data_dict[ticker].append(float(price))

        context["task_instance"].xcom_push(key="prices_dict", value=data_dict)

    get_training_data_from_db = PythonOperator(
        task_id = "get_training_data_from_db",
        python_callable=_get_training_data_from_db,
        op_kwargs = {"db_conn_id": 'pg-metal_prices'}
    )

    def _train_and_save_model(output_path, **context) -> None:
        """
        Gets training data from the XCom, converts it into suitable
        Pandas Dataframe, uses the data to train model and saves the
        trained model into the filesystem.

        Arguments:
            output_path - a directory, that the trained model files
                        will be saved, passed as a keyword argument
                        from the DAG
            **context - DAG context

        Returns:
            nothing
        """
        logger = logging.getLogger(__name__)
        data_dict = context["task_instance"].xcom_pull(task_ids="get_training_data_from_db",
                                                  key="prices_dict")

        dataframe = pd.DataFrame.from_dict(data_dict)

        model = Model(tickers=data_dict.keys())
        logger.info("Starting training model")
        model.train(data=dataframe)
        logger.info("Finished training model")

        logger.info("Saving model")
        output_path = f"{output_path}trained_model_{str(datetime.now())}"
        model.save(path_to_dir=output_path)
        logger.info("Finished saving model")

    train_and_save_model = PythonOperator(
        task_id = "train_and_save_model",
        python_callable=_train_and_save_model,
        op_kwargs = {"output_path": "/opt/airflow/output/"}
    )

    get_training_data_from_db >> train_and_save_model