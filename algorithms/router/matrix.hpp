// The stop-to-stop matrices (<mode>.bin, float32 (3, N, N): walk_m, bike_m, wait_s; written by `street_router
// matrix`), mapped read-only once at startup and kept for the server's life. RAPTOR reads its footpaths and the
// Veturilo rides from them; a row is re-timed with the query's speeds: walk_m / v_walk + bike_m / v_bike + wait_s.
#pragma once

#include <cmath>
#include <cstdint>
#include <filesystem>
#include <format>
#include <fstream>
#include <limits>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <nlohmann/json.hpp>

#include "graph.hpp"
#include "stations.hpp"

class Matrix {
public:
    Matrix() = default;
    Matrix(const Matrix&) = delete;
    Matrix& operator=(const Matrix&) = delete;
    ~Matrix() {
        if (data_) ::munmap(const_cast<float*>(data_), bytes_);
    }

    // Maps dir/<mode>.bin when it belongs to the loaded overlay; otherwise `error` says why (the mode cannot plan).
    // Checks: file size = 3 N^2 * 4 with N = overlay size, meta.json stations_hash = overlay hash, points.csv ids =
    // overlay ids in order (the matrix rows). meta.json's per-mode fields are not used.
    bool open(const std::filesystem::path& dir, const std::string& mode, const Stations& st) {
        const auto file = dir / (mode + ".bin");
        n_ = st.list.size();
        if (!std::filesystem::exists(file)) return fail(std::format("no {}.bin", mode));
        const auto size = std::filesystem::file_size(file);
        if (size != 3ULL * n_ * n_ * sizeof(float))
            return fail(std::format("{}.bin has {} bytes, expected 3 x {}^2 x 4 = {}", mode, size, n_, 3ULL * n_ * n_ * 4));
        std::ifstream meta_in(dir / "meta.json");
        const auto meta = meta_in ? nlohmann::json::parse(meta_in, nullptr, false) : nlohmann::json();
        if (!meta.is_object() || meta.value("stations_hash", "") != st.hash)
            return fail("meta.json stations_hash differs from stations.json (matrices built for another overlay)");
        std::ifstream points(dir / "points.csv");
        if (!points) return fail("no points.csv");
        std::string line;
        std::getline(points, line);  // header
        for (std::size_t i = 0; i < n_; ++i) {
            if (!std::getline(points, line)) return fail("points.csv has fewer rows than stations.json");
            const auto a = line.find(','), b = line.find(',', a + 1);
            if (a == std::string::npos || line.substr(a + 1, b - a - 1) != st.list[i].id)
                return fail(std::format("points.csv row {} is not {}", i, st.list[i].id));
        }
        const int fd = ::open(file.c_str(), O_RDONLY);
        if (fd < 0) return fail(std::format("cannot open {}.bin", mode));
        void* p = ::mmap(nullptr, size, PROT_READ, MAP_SHARED, fd, 0);
        ::close(fd);
        if (p == MAP_FAILED) return fail(std::format("cannot map {}.bin", mode));
        data_ = static_cast<const float*>(p), bytes_ = size;
        error.clear();
        return true;
    }

    [[nodiscard]] bool ok() const { return data_ != nullptr; }
    [[nodiscard]] std::size_t size() const { return n_; }
    // Row i of each plane: walk_m, bike_m, wait_s from location i to every location (NaN = no path).
    [[nodiscard]] const float* walk(std::size_t i) const { return data_ + i * n_; }
    [[nodiscard]] const float* bike(std::size_t i) const { return data_ + n_ * n_ + i * n_; }
    [[nodiscard]] const float* wait(std::size_t i) const { return data_ + 2 * n_ * n_ + i * n_; }
    // Seconds from i to j with these speeds; +inf without a path.
    [[nodiscard]] double seconds(std::size_t i, std::size_t j, const Speeds& s) const {
        const double w = walk(i)[j];
        if (std::isnan(w)) return std::numeric_limits<double>::infinity();
        return w / s.walk + bike(i)[j] / s.bike + wait(i)[j];
    }

    std::string error = "not loaded";

private:
    bool fail(std::string why) {
        error = std::move(why);
        return false;
    }
    const float* data_ = nullptr;
    std::size_t bytes_ = 0, n_ = 0;
};
