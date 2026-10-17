cmake_minimum_required(VERSION 3.20)
project(street_matrix LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_executable(street_matrix street_matrix.cpp)
target_compile_options(street_matrix PRIVATE -Wall -Wextra -Wpedantic)
