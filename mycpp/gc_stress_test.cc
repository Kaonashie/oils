// gc_stress_test.cc: Do many allocations and collections under ASAN
//
// And with GC_STATS defined.

#include "mycpp/runtime.h"
#include "vendor/greatest.h"

// TODO:
// - Assert the number of collections
// - Assert the number of heap growths
// - maybe number of allocations?

int count(int n) {
  int dummy = 42;
  StackRoots _roots({&dummy});
  // log("d %p", &dummy);

  if (n == 0) {
    return 0;
  } else {
    return 1 + count(n - 1);
  }
}

TEST overflowing_roots_test() {
  gHeap.Init(KiB(1));

  log("count 4000 = %d", count(4000));

  // When our stack roots were limited, this would crash
  log("count 5000 = %d", count(5000));
  log("count 20000 = %d", count(20000));
  log("count 25000 = %d", count(25000));
  // Stack overflow in ASAN
  // log("count 29000 = %d", count(29000));
  // Stack overflow in dbg
  // log("count 200000 = %d", count(200000));

  PASS();
}

TEST str_simple_test() {
  gHeap.Init(KiB(1));

  Str* s = nullptr;
  StackRoots _roots({&s});

  int total = 0;
  for (int i = 0; i < 400; ++i) {
    unsigned char c = i % 256;
    s = chr(c);
    /* log("i = %d", i); */
    ASSERT_EQ_FMT(c, ord(s), "%d");  // Check for memory corruption
    total += len(s);
  }

  log("total = %d", total);
#ifdef GC_STATS
  gHeap.Report();
#endif

  PASS();
}

GLOBAL_STR(b, "b");
GLOBAL_STR(bx, "bx");

TEST str_growth_test() {
  gHeap.Init(KiB(1));

  Str* s = nullptr;
  StackRoots _roots({&s});

#ifdef GC_STATS
  gHeap.Report();
#endif

  s = StrFromC("b");
  int n = 300;
  int total = 0;
  for (int i = 0; i < n; ++i) {
    total += len(s);  // count it first

    // log("--- %p %d", s, len(s));
    // print(s);
    s = s->replace(b, bx);
    // print(s);
  }
  log("total = %d", total);

  int expected = (n * (n + 1)) / 2;
  ASSERT_EQ_FMT(expected, total, "%d");

#ifdef GC_STATS
  gHeap.Report();
#endif

  PASS();
}

// Simple test with just List on the heap.
TEST list_append_test() {
  gHeap.Init(KiB(1));

  List<int>* L = nullptr;
  StackRoots _roots({&L});

  int length = 1;
  L = NewList<int>(42, length);

  int n = 1000;
  int total = 0;
  for (int i = 0; i < n; ++i) {
    total += len(L);  // count it first

    // log("sliced L = %p", L);
    L->append(43);  // append to end
  }
  log("total = %d", total);
  ASSERT_EQ_FMT(500500, total, "%d");

  PASS();
}

TEST list_slice_append_test() {
  gHeap.Init(KiB(1));

  List<int>* L = nullptr;
  StackRoots _roots({&L});

  int length = 5;
  L = NewList<int>(42, length);

  int n = 300;
  int total = 0;
  for (int i = 0; i < n; ++i) {
    /* log("i = %d", i); */
    total += len(L);  // count it first

    L = L->slice(1);
    assert(len(L) == 4);

    L->append(43);  // append to end
    assert(len(L) == 5);
  }
  log("total = %d", total);

  int expected = n * length;
  ASSERT_EQ_FMT(expected, total, "%d");

  PASS();
}

TEST list_str_growth_test() {
  gHeap.Init(KiB(1));

  Str* s = nullptr;
  List<Str*>* L = nullptr;
  StackRoots _roots({&s, &L});
  // StackRoots _roots({&L});

  s = StrFromC("b");
  L = Alloc<List<Str*>>();

#if 0
  int total = 0;
  int n = 40;
  for (int i = 0; i < n; ++i) {
    log("i = %d", i);
    //total += len(s);

    L->append(s);

    // This works if we don't have 's'.  Because it's global?
    //L->append(bx);
  }
  log("total = %d", total);

  int expected = (n * (n + 1)) / 2;
  ASSERT_EQ_FMT(expected, total, "%d");
#endif

  PASS();
}

TEST dict_growth_test() {
  gHeap.Init(KiB(1));

  Str* s = nullptr;
  Dict<Str*, int>* D = nullptr;
  StackRoots _roots({&s, &D});

  s = StrFromC("abcdefg");
  D = Alloc<Dict<Str*, int>>();

  int total = 0;
  for (int i = 0; i < 40; ++i) {
    total += len(s);
    s = s->replace(b, bx);
    D->set(s, 42);
  }
  log("total = %d", total);

  // TODO: Test NewDict(), etc.

  PASS();
}

GREATEST_MAIN_DEFS();

int main(int argc, char** argv) {
  gHeap.Init(KiB(1));

  GREATEST_MAIN_BEGIN();

  RUN_TEST(overflowing_roots_test);
  RUN_TEST(str_simple_test);
  RUN_TEST(str_growth_test);
  RUN_TEST(list_append_test);
  RUN_TEST(list_slice_append_test);
  RUN_TEST(list_str_growth_test);
  RUN_TEST(dict_growth_test);

  gHeap.Collect();

  GREATEST_MAIN_END(); /* display results */
  return 0;
}
