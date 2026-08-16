# Quality Metrics

The Dataset Quality Service starts each dataset at 100 and subtracts configured penalties for:

- Missing datasets
- Missing required fields
- Duplicate records
- Broken Product ID references
- Schema violations
- Missing product relationships

The service does not repair data. It reports issues so upstream services or source data can be corrected.

