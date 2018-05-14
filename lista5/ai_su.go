package main

import (
	"flag"
	"fmt"
	"os"
	"os/user"
	"path"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
)

const (
	prac            = "prac"
	restricted_path = "/pio/scratch/2/ai_solutions/"
)

func panicNonNull(err error) {
	if err != nil {
		panic(err)
	}
}

func usage(cond bool, message string) {
	if cond {
		if len(message) > 0 {
			fmt.Fprintln(os.Stderr, message)
			fmt.Fprintln(os.Stderr, "")
		}
		fmt.Fprintf(os.Stderr, "usage: ai_su solution_dir\n")
		flag.PrintDefaults()
		os.Exit(2)
	}
}

func printIds() {
	fmt.Fprintf(
		os.Stderr,
		"I am uid=%d euid=%d gid=%d egid=%d\n",
		syscall.Getuid(), syscall.Geteuid(),
		syscall.Getgid(), syscall.Getegid(),
	)
}

func pracGid() int {
	prac_gid_s, gerr := user.LookupGroup(prac)
	panicNonNull(gerr)
	prac_gid, cerr := strconv.Atoi(prac_gid_s.Gid)
	panicNonNull(cerr)
	return prac_gid
}

func maybeSuid(sol_info os.FileInfo) {
	if syscall.Geteuid() != 0 {
		return
	}

	prac_gid := pracGid()
	sol_owner := int(sol_info.Sys().(*syscall.Stat_t).Uid)
	sol_group := int(sol_info.Sys().(*syscall.Stat_t).Gid)

	var dest_gid, dest_uid int
	if sol_group == prac_gid {
		// Rozwiązanie wzorcowe - dajemy upranienia do uruchomienia,
		// ale bez zmiany użytkownika!
		dest_uid = syscall.Getuid()
		dest_gid = sol_group
	} else {
		// Rozwiązanie studenta
		if syscall.Getgid() == prac_gid {
			// Pracownik może wszystko
			dest_uid = sol_owner
			dest_gid = sol_group
		} else {
			// Student może tyle co zwykle
			dest_uid = syscall.Getuid()
			dest_gid = syscall.Getgid()
		}
	}

	runtime.LockOSThread()
	if runtime.NumGoroutine() > 1 {
		panic("Too many goroutines, unsafe to setuid!")
	}
	_, _, errNo := syscall.RawSyscall(
		syscall.SYS_SETGID, uintptr(dest_gid), 0, 0)
	if errNo != 0 {
		panic(errNo)
	}
	// printIds()

	_, _, errNo = syscall.RawSyscall(
		syscall.SYS_SETUID, uintptr(dest_uid), 0, 0)
	if errNo != 0 {
		panic(errNo)
	}
	// printIds()
}

func checkSolutionPermissions(solution_dir string, sol_info os.FileInfo) {
	prac_gid := pracGid()
	sol_group := int(sol_info.Sys().(*syscall.Stat_t).Gid)

	if sol_group == prac_gid {
		usage(
			sol_info.Mode().Perm()&0x7 > 0, fmt.Sprintf(
				"The teacher's solution folder must not be world-readable!\n"+
					"Please execute: chmod -R o-rwx %s\n", solution_dir))
	} else {
		usage(
			sol_info.Mode().Perm()&0x3F > 0, fmt.Sprintf(
				"The student's solution folder must not be world "+
					"nor group-readable!\nPlease execute: "+
					"chmod -R g-rwx,o-rwx %s\n", solution_dir))
	}
}

func main() {
	var _ = flag.Int64("memlimit", 0, "Limit RAM (in MB).")
	flag.Parse()
	usage(len(flag.Args()) != 1, "")

	solution_dir, abs_err := filepath.Abs(flag.Args()[0])
	usage(abs_err != nil, "Path not found")

	dir_info, dir_err := os.Stat(solution_dir)
	usage(
		dir_err != nil || !dir_info.IsDir(),
		"Specified folder does not exist!")
	usage(!strings.HasPrefix(solution_dir, restricted_path),
		fmt.Sprintf("The solution folder %s must lie below %s.",
			solution_dir, restricted_path))
	checkSolutionPermissions(solution_dir, dir_info)

	// printIds()
	maybeSuid(dir_info)
	// printIds()

	solution_entrypoint := path.Join(solution_dir, "run.sh")
	_, f_err := os.Stat(solution_entrypoint)
	usage(f_err != nil, "Specified folder has to contain a run.sh file!")

	binary := "/bin/bash"
	argv := []string{
		"bash", solution_entrypoint,
	}
	env := []string{
		"PATH=/usr/bin:/bin",
	}

	os.Chdir(solution_dir)
	err := syscall.Exec(binary, argv, env)
	panicNonNull(err)
}
