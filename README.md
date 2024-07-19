### Portfolio project
# Apache Airflow pipelines for data collection and machine learning model training

This is repository for Turing College Data Engineering course **Capstone Project**.

The point of this project is to prepare an Apache Airflow data pipeline for the machine learning algorithm and further analysis. I am required to choose the source of the project, implement the data pipeline that would upload the data to the database, and create a separate pipeline to train an save the model. The data I am working with is precious metal prices and the model is given by the team as a Python program, that I need to extend and adjust, so it can read the training data from the database.

I also created a [plan](doc/PLAN.md) for the deliverables.

## Environment

I am developing on GNU/Linux Ubuntu 22.04 Server Edition using Oracle Free Tier ARM64 machine VM.Standard.A1.Flex with 4 ARM cores and 24 GB of RAM. The machine is working beautifuly for me for the whole Turing College course. I am using Docker and Docker compose to run Apache Airflow and pgAdmin4, while the PostgreSQL database is installed straight from the repository. Some plumbing is required to make pgAdmin and Airflow to work outside of their respective network and access the host.

Exact versions:
* PostgreSQL 14.9 (Ubuntu 14.9-0ubuntu0.22.04.1),
* pgAdmin4 7.7 from Docker Hub, image `dpage/pgadmin4`,
* Apache Airflow 2.7.1 from Docker Hub, installed from [the official documentation](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html),
* Python 3.8.18, provided by the Airflow container,
* Docker 24.05 from the Ubuntu repository along with Docker Compose 1.29.2 as a plugin (not yet integrated into Docker - it happened in the following versions).

I am developing with Visual Studio Code with Remote SSH connection to the Oracle machine.

### Airflow Docker Compose stack
The official Docker Compose [stack definition](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html) in the form of `docker-compose.yaml` need some alteration to run this project. You can find the exact file I used [here](docker/docker-compose.yaml).

There are some aspects you need to take into consideration:
1. Line 74: `_PIP_ADDITIONAL_REQUIREMENTS: ${_PIP_ADDITIONAL_REQUIREMENTS:- sktime pmdarima}`. You need to add `sktime` and `pmdarima` Python packages to the Apache Airflow Python environment, that is separate to the host Python environment (it is present within the container). Proper way to do it would be with the `docker-compose.yaml` variable `_PIP_ADDITIONAL_REQUIREMENTS`. For some unknown reason adding that inside the worker container with pip doesn't work - the module is not accessible in PythonOperator.
2. Line 78: I am mounting the `dags` folder from this repository to the `/opt/airflow/dags` folder within a container, where Apache Airflow looks for DAG files. I don't want Apache Airflow to alter this folder, so I keep the ownership with default folder rights to the default `ubuntu` user from the host.
3. Line 79: I am mounting the `output` folder from this repository to the `/opt/airflow/output` folder within a container, where it gets populated with trained model files. I want this folder to be writable from the containter, so I have relaxed the folder rights to `777`.

## Data source
I have decided to use [ChartSeeker](http://chartseeker.com/), that gives me the current metal prices. It is not really documented, however I was able to find out the data from the site requests. I would not use their data, if there was real decisions involved though - I am unable to tell, where it comes from, nor any other details. I just learned, that there are other projects that use it as a source.

The details needs to be defined in an Apache Airflow HTTP connection metastore with name `chartseeker`.

## Database structure
The metal prices data is stored in the PostgreSQL database in `prices` table. Connection is defined in Airflow as a Postgres type with name `pg_turing-metal_prices` and it is used within DAGs. The database should have it's own unique login, that would be able to query and insert the data defined with Airflow Connection. I may be used for analytic purposes.

The structure of `prices` table is simple:
* a `timestamp` (`timestamp without timezone` type) column with timestamp the price was taken,
* a `ticker` (`varchar(9)` type) column with the ticker's name,
* a `price` (`numeric(7,2)` type) with a price in USD.

The view for training the model `training_data` follows similar structure, it just gives the data for the last 12 hours and does not expose timestamp. It is created with an SQL query:
```sql
CREATE VIEW training_data AS
	SELECT ticker, price from prices
	WHERE timestamp >= (NOW() - INTERVAL '12 hours' )
	ORDER BY timestamp ASC;
```

## Airflow structure
There are two DAGs defined:
1. `get_prices` - it fetches the data from the source, and saves it into the `prices` table within the database. There are two atomic tasks - `fetch_data` and `upload_data_to_db` that communicate with XComs. It is scheduled to run every quarter.
2. `train_and_save_model` - it fetches the training data from `training_data` view from the database and use it to train and save the models for each metal. There are two tasks - `get_training_data_from_db` and `train_and_save_model`. The models are saved in [the output directory](dags/output/) for later use. It is triggered after tasks in `get_prices` are finished.

## Backups
The database and model files are backed up every 6 hours with the [backup script](backup/backup) and last 20 elements are preserved. The backup script gets triggered by user crontab:
```bash
0 */6 * * * /home/ubuntu/jakluz-DE2.4/backup/backup
```

Backup script needs to be executable.

## Notes and lessons learned
1. The PostgreSQL `money` column type is not as great, as name suggests and even discouraged by the PostgreSQL community. It's better to use `numeric(7,2)` to have a good money representation in this project. That is what I did after experimenting with `money`.
2. Python 3.8 has issues with type hints notation like: `list[str]`, because of different typing implementation. I had to fix the model source with `from typing import List, Tuple, Dict` and then instantiating those in type hints like: `List[str]`. In Python 3.8 types were not subsctiptable. I could just remove the subscripting, but I did not want to loose information.
3. Custom hooks, that are provided with Airflow packages are more usable than Operators - Operators are severly limited. E. g. `PostgresHook` exposes really useful methods (like `insert_rows`), that handles insertion to the database in a convienent way, while `PostgresOperator` can just run an SQL query or SQL query file, although it may be parametrized. Still, it is severly limited and implementation comments states, that it is deprecated. `PosgresHook` inherits from `DbApiHook`, and most methods come from the later. It is possible, that I should use it rather then `PostgresHook`, but I am not really sure. This is confusing, and Airflow documentation is not really helpful in that regard. It rarely is to be honest.
4. I believe the XComs are persistent. While it may not be any issue for a small amount of data stored there with this project, but it may become an issue with bigger datasets. One needs to be extra careful with the amount of data put there, or implement a cleanup solution. UPDATE: I have noticed, that XComs are getting deleted from the UI. I still don't know, when does it happen. The [XCom documentation](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/xcoms.html) doesn't specify that.
5. Getting an error and catching it with Exception does not mark task as failed - the flow is not stopped, the show goes on. If I want to manage flow and e.g. stop further tasks from running, I need to use `AirflowException` or it's subclasses. So, the proper way to do it is to catch exception, handle it and raise approperiate Airflow exception.
