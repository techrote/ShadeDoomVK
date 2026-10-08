#pragma once

// SDVK-002: standard-library-only evidence primitives. These do not own or
// change renderer state. The executable CPU fixture exercises the same code.
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <locale>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace SdvkObservation
{
inline std::string Quote(const std::string& value)
{
    std::ostringstream out;
    out.imbue(std::locale::classic());
    out << '"';
    for (size_t i = 0; i < value.size(); ++i)
    {
        const auto c = static_cast<unsigned char>(value[i]);
        if (c == '"' || c == '\\') out << '\\' << char(c);
        else if (c < 32 || c == 127)
            out << "\\u00" << std::hex << std::setw(2) << std::setfill('0') << unsigned(c) << std::dec;
        else if (c < 128) out << char(c);
        else
        {
            // JSON text is UTF-8. Preserve complete code points rather than
            // reinterpreting their bytes as Latin-1 escape sequences.
            const size_t length = c >= 0xc2 && c <= 0xdf ? 2 :
                c >= 0xe0 && c <= 0xef ? 3 : c >= 0xf0 && c <= 0xf4 ? 4 : 0;
            if (!length || length > value.size() - i)
                throw std::runtime_error("Invalid UTF-8 SDVK observation string");
            for (size_t offset = 1; offset < length; ++offset)
            {
                const auto continuation = static_cast<unsigned char>(value[i + offset]);
                if (continuation < 0x80 || continuation > 0xbf)
                    throw std::runtime_error("Invalid UTF-8 SDVK observation string");
            }
            const auto second = static_cast<unsigned char>(value[i + 1]);
            if ((c == 0xe0 && second < 0xa0) || (c == 0xed && second >= 0xa0) ||
                (c == 0xf0 && second < 0x90) || (c == 0xf4 && second >= 0x90))
                throw std::runtime_error("Invalid UTF-8 SDVK observation string");
            out.write(value.data() + i, static_cast<std::streamsize>(length));
            i += length - 1;
        }
    }
    out << '"';
    return out.str();
}

inline std::string Number(double value)
{
    if (!std::isfinite(value)) throw std::runtime_error("Nonfinite SDVK observation value");
    std::ostringstream out;
    out.imbue(std::locale::classic());
    out << std::setprecision(17) << value;
    return out.str();
}

class Object
{
public:
    Object& Raw(const char* key, const std::string& value)
    {
        if (!Body.empty()) Body += ',';
        Body += Quote(key); Body += ':'; Body += value;
        return *this;
    }
    Object& Str(const char* key, const std::string& value) { return Raw(key, Quote(value)); }
    Object& Bool(const char* key, bool value) { return Raw(key, value ? "true" : "false"); }
    Object& Num(const char* key, double value) { return Raw(key, Number(value)); }
    template<class T> Object& Int(const char* key, T value) { return Raw(key, std::to_string(value)); }
    std::string Json() const { return '{' + Body + '}'; }
private:
    std::string Body;
};

inline std::string Unavailable(const char* reason)
{
    return Object().Bool("available", false).Str("reason", reason).Json();
}

inline unsigned ParseCount(const char* text, unsigned minimum, unsigned maximum)
{
    if (!text || !*text) throw std::runtime_error("Missing SDVK observation count");
    unsigned result = 0;
    for (const unsigned char* c = reinterpret_cast<const unsigned char*>(text); *c; ++c)
    {
        if (*c < '0' || *c > '9' || unsigned(*c - '0') > maximum || result > (maximum - unsigned(*c - '0')) / 10)
            throw std::runtime_error("SDVK observation count is not a bounded decimal integer");
        result = result * 10 + unsigned(*c - '0');
    }
    if (result < minimum || result > maximum) throw std::runtime_error("SDVK observation count outside its declared range");
    return result;
}

inline bool SafePrefix(const std::string& prefix)
{
    return !prefix.empty() && prefix.size() <= 1024 &&
        prefix.find_first_of("\";\r\n\t") == std::string::npos;
}

// C11 exclusive creation is supported by the project's current native C
// runtimes. Unlike exists()+ofstream this cannot truncate a competing file.
inline void WriteFresh(const std::filesystem::path& path, const std::string& value)
{
#ifdef _WIN32
    std::FILE* file = nullptr;
    _wfopen_s(&file, path.c_str(), L"wbx");
#else
    std::FILE* file = std::fopen(path.c_str(), "wbx");
#endif
    if (!file) throw std::runtime_error("SDVK evidence destination already exists or cannot be created");
    const bool written = std::fwrite(value.data(), 1, value.size(), file) == value.size();
    const bool closed = std::fclose(file) == 0;
    if (!written || !closed) throw std::runtime_error("SDVK evidence write/close failed; partial output is not valid evidence");
}

class RecordStore
{
public:
    static constexpr size_t DefaultMaxRecords = 65536;
    static constexpr size_t DefaultMaxBytes = 16 * 1024 * 1024;
    static constexpr size_t MaxRecordBytes = 16384;

    explicit RecordStore(size_t maxRecords = DefaultMaxRecords, size_t maxBytes = DefaultMaxBytes)
        : MaxRecords(maxRecords), MaxBytes(maxBytes) { }

    bool Add(const char* kind, uint64_t frame, const std::string& data, bool deduplicate = false)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        if (Closed) return false;
        if (!Error.empty()) { ++Dropped; return false; }
        if (!kind || data.size() < 2 || data.front() != '{' || data.back() != '}' || data.size() > MaxRecordBytes)
            return Reject("Invalid or oversized SDVK observation record");
        const std::string type(kind);
        // Only adjacent identical observations may be coalesced. A global
        // value lookup would erase the distinction between A,B,A and A,A,B.
        if (deduplicate && !Rows.empty())
        {
            auto& previous = Rows.back();
            if (previous.Frame == frame && previous.Kind == type && previous.Data == data)
            {
                ++previous.Count;
                return true;
            }
        }
        const size_t bytes = data.size() + type.size();
        if (Rows.size() >= MaxRecords || bytes > MaxBytes - Bytes)
            return Reject("SDVK observation record/byte limit reached");
        Rows.push_back({ type, frame, 1, data });
        Bytes += bytes;
        return true;
    }

    void Fail(const std::string& error)
    {
        std::lock_guard<std::mutex> lock(Mutex);
        if (Error.empty()) Error = error;
    }
    std::string Failure() const { std::lock_guard<std::mutex> lock(Mutex); return Error; }
    uint64_t DroppedCount() const { std::lock_guard<std::mutex> lock(Mutex); return Dropped; }
    size_t Size() const { std::lock_guard<std::mutex> lock(Mutex); return Rows.size(); }
    size_t ByteCount() const { std::lock_guard<std::mutex> lock(Mutex); return Bytes; }

    std::string CloseJson()
    {
        std::lock_guard<std::mutex> lock(Mutex);
        Closed = true;
        std::string result = "[";
        for (const auto& row : Rows)
        {
            if (result.size() > 1) result += ',';
            result += Object().Str("kind", row.Kind).Int("frame", row.Frame).Int("count", row.Count).Raw("data", row.Data).Json();
        }
        return result + ']';
    }
private:
    struct Row { std::string Kind; uint64_t Frame, Count; std::string Data; };
    bool Reject(const char* reason) { Error = reason; ++Dropped; return false; }
    mutable std::mutex Mutex;
    std::vector<Row> Rows;
    size_t MaxRecords, MaxBytes, Bytes = 0;
    uint64_t Dropped = 0;
    bool Closed = false;
    std::string Error;
};
}
