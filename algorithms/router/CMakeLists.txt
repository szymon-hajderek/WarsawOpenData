cmake_minimum_required(VERSION 3.20)
project(street_router LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

# Two single-header libraries for `serve`: cpp-httplib (plain HTTP, no compression) and nlohmann/json.
include(FetchContent)
set(HTTPLIB_USE_OPENSSL_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
set(HTTPLIB_USE_ZLIB_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
set(HTTPLIB_USE_BROTLI_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
set(HTTPLIB_USE_ZSTD_IF_AVAILABLE OFF CACHE BOOL "" FORCE)
FetchContent_Declare(httplib URL https://github.com/yhirose/cpp-httplib/archive/refs/tags/v0.61.0.tar.gz
                     DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_Declare(json URL https://github.com/nlohmann/json/releases/download/v3.12.0/json.tar.xz
                     DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(httplib json)

add_executable(street_router main.cpp)
target_compile_options(street_router PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(street_router PRIVATE httplib::httplib nlohmann_json::nlohmann_json)
