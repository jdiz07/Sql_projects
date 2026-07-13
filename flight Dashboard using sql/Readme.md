## Projects

### 1. SQL Project 1
### 1. Flight Dashboard

The first SQL project in this repository. Its folder contains the SQL scripts and any supporting files needed to run the project.
An interactive dashboard for exploring flight data. The project cleans the raw dataset with SQL before using the prepared data in a Streamlit application for analysis and visualization.

**Topics covered:**
**What this project includes:**

- Database and table creation
- Data insertion and updates
- SQL queries for analysis and reporting
- Joins, aggregations, and filtering
- Cleaning and preparing a flight dataset with SQL
- Handling missing, inconsistent, or duplicate data
- SQL queries for flight-data analysis
- An interactive Streamlit dashboard built from the cleaned dataset
- Visual exploration of flight information and trends

## Repository structure

```text
sql_project/
├── project-1/
│   ├── README.md
│   └── *.sql
├── flight-dashboard/
│   ├── data/
│   ├── sql/
│   ├── app.py
│   └── README.md
└── README.md
```

1. Open the relevant project folder.
2. Read that project's `README.md` for setup requirements and instructions.
3. Run the SQL scripts in the order described there using your preferred database tool.
4. Start the Streamlit dashboard:

   ```bash
   streamlit run app.py
   ```

## Tools

Projects may use tools such as MySQL, PostgreSQL, SQL Server, or SQLite. Each project will specify its database system and requirements.
This project uses SQL for data cleaning and analysis, and Streamlit for the interactive dashboard. The project folder will specify the database system and any additional requirements.

## Future projects