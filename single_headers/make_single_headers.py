#! /usr/bin/python3

import tempfile
import subprocess
import os,re,sys,shutil, os.path

from os.path import join

WITH_LINE_DIRECTIVES = False

LINUX_ONLY_HEADERS = ['sys/epoll.h']
APPLE_ONLY_HEADERS = ['sys/event.h']

def include_directive(d):
    linux_only = False
    apple_only = False
    for lh in LINUX_ONLY_HEADERS:
        if lh in d:
            linux_only = True
    for ah in APPLE_ONLY_HEADERS:
        if ah in d:
            apple_only = True
    if linux_only:
        return f"#if __linux__\n{d}#endif\n"
    if apple_only:
        return f"#if __APPLE__\n{d}#endif\n"
    return d

def process_file(library_name, f, processed, output):

    if f in processed:
        return
    processed.append(f)

    if not os.path.isfile(f):
        raise Exception(f"file not found {f} when building {library_name}")

    header_guard = "LITHIUM_SINGLE_HEADER_GUARD_" + re.match(".*include/(li/.+)", f).group(1).upper().replace('/', '_').replace('.', "_");
    output += f"#ifndef {header_guard}\n" 
    output += f"#define {header_guard}\n"
    contiguous = False 
    for line_number, line in enumerate(open(f, "r")):
        #line = line.replace("li::", f"{library_name}::")
        line = line.replace("lithium_symbol.hh", "li/symbol/symbol.hh")
        line = line.replace("// Generated by the lithium symbol generator.", "")

        m = re.match("^#include\s*<(li/.*)>.*$", line)
        if m:
            process_file(library_name, join(install_dir, "include", m.group(1)), processed, output)
            contiguous = False;
        elif re.match("#pragma once", line):
            contiguous = False;
            pass
        else:
            if WITH_LINE_DIRECTIVES and not contiguous:
                output += f"#line {line_number + 1} \"{f}\"\n"
            output += [line];
            contiguous = True;

    output += f"\n#endif // {header_guard}\n\n"

def install_lithium():
    # create temp directory.
    tmp_dir=tempfile.mkdtemp()
    src_dir=join(tmp_dir, "src")
    build_dir=join(tmp_dir, "build")
    install_dir=join(tmp_dir, "install")

    os.mkdir(src_dir)
    os.mkdir(build_dir)
    os.mkdir(install_dir)

    processed=[]

    # git clone recursive iod
    subprocess.check_call(["git", "clone", "https://github.com/matt-42/lithium", src_dir])

    # cd build_dir
    os.chdir(build_dir)

    # Install
    subprocess.call(["cmake", src_dir, "-DCMAKE_INSTALL_PREFIX=" + install_dir])
    subprocess.check_call(["make", "install", "-j4"])
    return tmp_dir

def make_single_header(install_dir, library_name, input_files, output_path):

    processed=[]

    # Generate single file header.
    lines=[]
    for f in input_files:
        process_file(library_name, join(install_dir, f"include/{f}"), processed, lines)

    body=[]
    includes=[]
    windows_includes_ref=["ciso646", "io.h", "windows.h"]
    windows_includes=[]
    for line in lines:
        m = re.match("^\s*#include <(.*)>$", line)
        if m:
            if m.groups()[0] in windows_includes_ref:
                windows_includes.append(line)
            else:
                includes.append(line)
        else:
            body.append(line)

    result = ""
    result += "// Author: Matthieu Garrigues matthieu.garrigues@gmail.com\n//\n"
    result += f"// Single header version the {library_name} library.\n"
    result += "// https://github.com/matt-42/lithium\n"
    result += "//\n"    
    result += "// This file is generated do not edit it.\n\n"
    result += "#pragma once\n\n"

    # postgres.h first to avoid compilation errors.
    for l in sorted(set(includes)):
        if "postgres.h" in l:
            result += include_directive(l);
    for l in sorted(set(includes)):
        result += include_directive(l)
    if len(windows_includes):
        result += "\n#if defined(_MSC_VER)\n"
        for l in sorted(set(windows_includes)):
            result += l        
        result += "#endif // _MSC_VER\n"
    result += "\n\n"
    for l in body:
        result += l

    # read previosu content
    previous_content = ""
    if os.path.exists(output_path):
        with open(output_path, 'r') as content_file:
            previous_content = content_file.read()
    # only write if new content is different.
    if previous_content != result:
        with open(output_path, 'w') as output:
            output.write(result)

if __name__ == "__main__":

    if len(sys.argv) == 4: # --with-line-directive as first options
        WITH_LINE_DIRECTIVES = True
        install_dir = sys.argv[2]
        output_dir = sys.argv[3]
    elif len(sys.argv) == 3:
        install_dir = sys.argv[1]
        output_dir = sys.argv[2]
    else:
        lithium_dir = install_lithium()
        install_dir = lithium_dir.name + "/install"
        output_dir = sys.argv[1]


    data = dict({ 
        "lithium_metamap": ["li/metamap/metamap.hh"],
        "lithium_symbol": ["li/symbol/symbol.hh"],
        "lithium_json": ["li/json/json.hh"],
        "lithium_http_client": ["li/http_client/http_client.hh"],
        "lithium_http_backend": ["li/http_backend/http_backend.hh"],
        "lithium_mysql": ["li/sql/mysql.hh","li/sql/sql_orm.hh"],
        "lithium_sqlite": ["li/sql/sqlite.hh","li/sql/sql_orm.hh"],
        "lithium_pgsql": ["li/sql/pgsql.hh","li/sql/sql_orm.hh"],
        "lithium": ["li/sql/sqlite.hh","li/http_client/http_client.hh","li/sql/sql_orm.hh", "li/sql/mysql.hh", "li/sql/pgsql.hh","li/http_backend/http_backend.hh"],
             })
    for libname, files in data.items():
        if not WITH_LINE_DIRECTIVES:
            make_single_header(install_dir, libname, files, f"{output_dir}/{libname}.hh")
        else:
            output_path = f"{output_dir}/{libname}.hh"
            result = '\n'.join([f"#include <{file}>" for file in files]) + "\n"
            # read previosu content
            previous_content = ""
            if os.path.exists(output_path):
                with open(output_path, 'r') as content_file:
                    previous_content = content_file.read()
            # only write if new content is different.
            if previous_content != result:
                with open(output_path, 'w') as output:
                    output.write(result)
