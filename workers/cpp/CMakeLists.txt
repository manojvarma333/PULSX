cmake_minimum_required(VERSION 3.16)
project(pulsex_cpp_worker CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

include(FetchContent)
FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(nlohmann_json)

find_package(Threads REQUIRED)

add_library(pulsex_worker_lib
    src/protocol.cpp
    src/strategies.cpp
    src/system_usage.cpp
    src/worker.cpp
)
target_include_directories(pulsex_worker_lib PUBLIC include)
target_link_libraries(pulsex_worker_lib PUBLIC nlohmann_json::nlohmann_json Threads::Threads)
target_compile_options(pulsex_worker_lib PRIVATE -Wall -Wextra)

add_executable(pulsex_cpp_worker src/main.cpp)
target_link_libraries(pulsex_cpp_worker PRIVATE pulsex_worker_lib)

enable_testing()
add_executable(pulsex_cpp_tests tests/test_protocol.cpp)
target_link_libraries(pulsex_cpp_tests PRIVATE pulsex_worker_lib)
add_test(NAME protocol_and_strategy_tests COMMAND pulsex_cpp_tests)
