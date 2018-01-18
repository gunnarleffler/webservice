#!/bin/bash
echo "This operation will wipe the existing hydro.db and create a new one."
read -r -p "Are you sure? [y/N] " response
if [[ $response =~ ^([yY][eE][sS]|[yY])$ ]]
then
  cd ../data
  echo "Removing old database"
  rm hydro.db
  echo "Creating new database from pisces.sqlite schema"
  sqlite3 hydro.db < ../docs/pisces.sqlite
else
   echo "Cancelled."
fi
