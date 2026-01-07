// api calling with async await
const getDetails = async () => {
    //request data gathering logic
    let userid = document.getElementById("userid").value;
    let para = document.getElementById("simple");
    let result = document.getElementById("sample");
    para.style.display = "block"
    //business logic
    try {
        await Promise.all([])

    }
    catch (err) {
        result.innerHTML = "<h3>something went wrong</h3>";
    }
}