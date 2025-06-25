#!/bin/bash

# Script to render PlantUML ERD for Sprint 2

# Navigate to the directory containing the plantuml.jar file
cd /home/siaziz/Desktop/backend

# Render the ERD diagram
java -jar plantuml.jar sprint2/sprint2_erd.plantuml

echo "ERD diagram generated successfully as sprint2/sprint2_erd.png"
