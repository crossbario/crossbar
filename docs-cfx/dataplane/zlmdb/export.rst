Database Export
===============

CrossbarFX will allow export of data persisted from a nodes embedded databases into
flat files in **Apache Parquet** format, with optional deflate or snappy compression.

Flat files are created in a file export area that must be accessible as a local
filesystem on the node.

Exported files in the file export area can be automatically uploaded and synchronized
to a **blob store** (eg AWS S3) which can serve as the data source or storage of a
Hadoop cluster for historical data analysis.

Hadoop file format
Apache Spark

Apache Parquet
https://parquet.apache.org/


Apache Parquet provides a partitioned binary columnar serialization for data frames. It is designed to make reading
and writing data frames efficient, and to make sharing data across data analysis languages easy. Parquet can use a
variety of compression techniques to shrink the file size as much as possible while still maintaining good
read performance.

https://pandas.pydata.org/pandas-docs/version/0.21/io.html#io-parquet
https://blog.cloudera.com/blog/2016/04/benchmarking-apache-parquet-the-allstate-experience/
