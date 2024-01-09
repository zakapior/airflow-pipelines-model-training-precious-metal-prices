# Plan
During the inspiring process of developing this project, I have come up with the following plan:

## 1. Thourughly analyze the reference model code to find out, what exactly the model needs.

It seems, that the model needs a dictionary with a ticker name and list of prices it had on the market. So, grabbing the prices from the source and present it in correct order and format is all I need to train and save the project.

## 2. Decide on the service, that shall provide me with the prices I need to train the model.

One factor that I need to consider is amount of requests I can send to the service for free. Another is price - I don't want to spend any money to complete the project. Then I will evaluate the APIs services expose - the simpler it is, the better.

The only free source, that I could find is [ChartSeeker](http://chartseeker.com/), that provides some, extremely poorly documented data as TXT file with current prices for various things, metals included. Though I don't know where does this data come from or is it any good, I decided to use it, since it is free and updated really frequently. This data won't be base to do some real reasoning, so I decided it is good enough for this project.

I just hope ChartSeeker does not block me...

## 3. Decide on the database I shall use for this project.

I will once again use the tried-and-true PostgreSQL, that I have used for my previous projects. While I would love to use SQL Server, but I am not able to do that because of the ARM architecture I will develop the project on. I will have a separate database with a source table, where I will put all the timestamped prices, and a view that will give me the proper source data to train the model, basicaly just the prices for the last 12 hours ordered by time.

## 4. Decide on the architecture of the DAGs within Airflow.

I intend to split the work into two DAGs

1. `get_prices` that will let me query the source periodicaly to get the prices and upload them to the database. This DAG will be run periodicaly with rather short interval to get enought data to train the model.

2. `train_model` that will train the model on the data provided by `get_prices` and save it into the filesystem.

## 5. Implement the process of getting the data from the source and uploading it into the database.

A separate DAG for getting the data from source run every quarter, backfilling would not be neccessary.

## 6. Implement the process of training the model.

Second independent DAG run on more infrequent basis should be quite enough.