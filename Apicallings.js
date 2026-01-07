//api calling with asynwait
const postsinfo = async()=> {
    try{
        const result = await fetch("https://jsonplaceholder.typicode.com/todos/1");
        const data = await result.json();
        console.log(data);

    }
    catch(error){
        console.log(error);
    }

};
postsinfo();