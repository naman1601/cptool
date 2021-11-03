# Hello, this is cptool
`cptool` is a python script that I use to parse competitive programming problems, along with testcases and extra data like time and memory limits of the problem.<br>
Additionally, it can also test a solution against the testcases, but that feature is implemented in a very basic form.<br>
This script uses data parsed by [Competitive Companion](https://github.com/jmerle/competitive-companion), and creates separate folders for all contests, and sub-folders for each problem of the contest. I use parts from [ecnerwala's script](https://gist.github.com/ecnerwala/ffc9b8c3f61e87ca043393a135d7794d) to fetch the data sent by Competitive Companion.<br>
This is a CLI tool. You can edit the source code to set your preferred programming language, and file paths according to your system! I use an alias which helps me to use the script regardless of my working directory. I will perhaps make this into a complete tool someday that would not require one to edit the source code to set it up!<br>
I would be really glad to have a look at any feedback/improvements to the tool. Thank you, and have fun!