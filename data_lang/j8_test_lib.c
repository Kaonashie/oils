#include <stddef.h>  // NULL for C++

const char* J8_TEST_CASES[] = {
    "x",
    "",
    "foozz abcdef abcdef \x01 \x02 \u03bc 0123456789 0123456 \xff",
    "foozz abcd \xfe \x1f",
    "\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0e\x0f\x10\xfe",
    "\xff\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0e\x0f\x10\xfe",
    "C:\\Program Files\\",
    "Fool's Gold",  // single quote
    NULL,
};
