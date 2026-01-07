//validation logic
function validate(){
    //request data gathering logic
    let user_name =document.getElementById("username").value;
    let password = document.getElementById("pass").value;
    //validation logic
    if(user_name == ""){
        alert("Please enter username");
        return false;
    }
    return true;



}