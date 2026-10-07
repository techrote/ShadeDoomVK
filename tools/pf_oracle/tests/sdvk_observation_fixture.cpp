// Executes the same bounded evidence primitive used by the native observer.
#include "hw_sdvkdiagnosticcore.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include <thread>

using namespace SdvkObservation;

template<class F> void Rejects(F operation)
{
    bool rejected = false;
    try { operation(); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
}

int main(int argc, char** argv)
{
    assert(argc == 2);
    assert(ParseCount("4096", 1, 4096) == 4096);
    assert(ParseCount("0", 0, 100000) == 0);
    Rejects([] { ParseCount("-1", 0, 4096); });
    Rejects([] { ParseCount("4097", 1, 4096); });
    Rejects([] { ParseCount("999999999999999999999", 0, 4096); });
    Rejects([] { ParseCount("1tail", 0, 4096); });
    Rejects([] { ParseCount("9", 0, 1); });
    assert(SafePrefix("build/native run"));
    assert(!SafePrefix("build/out\";quit"));
    assert(!SafePrefix("build/out\nquit"));
    Rejects([] { Number(std::numeric_limits<double>::infinity()); });
    Rejects([] { Number(std::numeric_limits<double>::quiet_NaN()); });
    assert(Quote("quote\" slash\\ line\n") == "\"quote\\\" slash\\\\ line\\u000a\"");
    const std::string unicode = "\xc3\xa9 \xe6\x9d\xb1\xe4\xba\xac \xf0\x9f\x8e\xae";
    assert(Quote(unicode) == '"' + unicode + '"');
    for (const auto malformed : { "\x80", "\xc0\xaf", "\xe0\x80\xaf", "\xed\xa0\x80",
            "\xf0\x80\x80\xaf", "\xf4\x90\x80\x80", "\xf5\x80\x80\x80", "\xe2\x82", "\xe2(\xa1" })
        Rejects([&] { Quote(malformed); });

    RecordStore positive(4, 4096);
    const auto row = Object().Str("semantic_key", "MAP01:light:0").Str("decision", "selected").Json();
    // Worker order cannot lose a decision or create separate duplicate rows.
    std::vector<std::thread> workers;
    for (int thread = 0; thread < 4; ++thread)
        workers.emplace_back([&] { for (int i = 0; i < 40; ++i) assert(positive.Add("light-query", 1, row, true)); });
    for (auto& worker : workers) worker.join();
    assert(positive.Size() == 1 && positive.DroppedCount() == 0 && positive.Failure().empty());
    assert(positive.Add("frame", 1, Object().Num("cpu_render_view_ms", 1.125).Int("gametic", 100).Json()));
    const auto json = positive.CloseJson();
    assert(json.find("\"count\":160") != std::string::npos);
    assert(json.find("\"cpu_render_view_ms\":1.125") != std::string::npos);
    assert(!positive.Add("frame", 2, "{}"));

    RecordStore sequenceABA, sequenceAAB;
    const auto first = Object().Str("semantic_key", "A").Json();
    const auto second = Object().Str("semantic_key", "B").Json();
    assert(sequenceABA.Add("light-query", 1, first, true));
    assert(sequenceABA.Add("light-query", 1, second, true));
    assert(sequenceABA.Add("light-query", 1, first, true));
    assert(sequenceAAB.Add("light-query", 1, first, true));
    assert(sequenceAAB.Add("light-query", 1, first, true));
    assert(sequenceAAB.Add("light-query", 1, second, true));
    assert(sequenceABA.Size() == 3 && sequenceAAB.Size() == 2);
    assert(sequenceABA.CloseJson() != sequenceAAB.CloseJson());

    RecordStore capacity(1, 4096);
    assert(capacity.Add("probe", 1, "{}"));
    assert(!capacity.Add("probe", 2, "{}"));
    assert(!capacity.Failure().empty() && capacity.DroppedCount() == 1);
    assert(!capacity.Add("probe", 3, "{}"));
    assert(capacity.DroppedCount() == 2 && capacity.Size() == 1);
    RecordStore byteLimit(100, 8);
    assert(!byteLimit.Add("context", 1, "{}", true));
    assert(byteLimit.Size() == 0 && byteLimit.DroppedCount() == 1);
    RecordStore shape;
    assert(!shape.Add("frame", 1, "[]"));
    assert(!shape.Failure().empty());

    const std::filesystem::path path(argv[1]);
    const auto envelope = Object().Str("schema", "sdvk-observation-core-fixture/v1")
        .Str("unicode", unicode)
        .Str("scope", "host-only evidence primitive control, not native renderer output").Raw("records", json).Json() + '\n';
    WriteFresh(path, envelope);
    Rejects([&] { WriteFresh(path, "overwritten"); });
    std::ifstream input(path, std::ios::binary);
    const std::string observed((std::istreambuf_iterator<char>(input)), {});
    assert(observed == envelope);
    std::cout << "SDVK observation positive/negative/concurrent/fresh-file controls PASS\n";
}
