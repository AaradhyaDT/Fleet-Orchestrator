import asyncio
from hr_api import post_submission

cpp_code = r'''#include <iostream>
#include <cstdlib>
#include <dirent.h>
using namespace std;

int main() {
    DIR* d = opendir(".");
    int count = 0;
    if (d) {
        while (readdir(d)) count++;
        closedir(d);
    }
    exit(min(count, 255));
}
'''

async def main():
    res = await post_submission('xtreme-shadows-2026', 'sunits-permutation-factory', cpp_code, language='cpp20')
    print('Signal (file count):', res.get('codechecker_signal'))
    print('compile msg:', res.get('compile_message'))

if __name__ == '__main__':
    asyncio.run(main())
