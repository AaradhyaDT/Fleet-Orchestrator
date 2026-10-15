#include<bits/stdc++.h>
#define cmin(a,b) (a>(b)?a=(b),1:0)
#define cmax(a,b) (a<(b)?a=(b),1:0)
#define dmin(a,b) ((a)<(b)?(a):(b))
#define dmax(a,b) ((a)>(b)?(a):(b))
namespace io{
	int F(){
		int n=0,F=0;
		char ch;
		while((ch=getchar())!='-'&&(ch<'0'||ch>'9'));
		ch=='-'?F=1:n=ch-'0';
		while((ch=getchar())>='0'&&ch<='9')n=n*10+ch-'0';
		return F?-n:n;
	}
	long long G(){
		long long n=0,F=0;
		char ch;
		while((ch=getchar())!='-'&&(ch<'0'||ch>'9'));
		ch=='-'?F=1:n=ch-'0';
		while((ch=getchar())>='0'&&ch<='9')n=n*10+ch-'0';
		return F?-n:n;
	}
}
std::unordered_map<long long,long long> s;
long long k;
long long F(long long n){
	if(n<3*k)return n-k+1;
	long long& f = s[n];
	if(f>0)return f;
	if(n%(2*k)==k)return f=1;
	long long x=(n+k)/(2*k);
	if(n%(2*k)==k+1){
		return f=std::min(F(n-x),F(n-x+1))+1;
	}
	else if((n-x)%(2*k)==k-1){
		return f=std::min(F(n-x),F(n-x-1))+1;
	}
	else{
		long long t = (n+k)-(2*k*x);
		if(t>=x){
			long long b=t/x;
			return f=F(n-b*x)+b;
		}
		return f=F(n-x)+1;
	}
}
int main(){
	int T=io::F();
	while(T--){
		s.clear();
		long long n=io::G();
		k=io::G();
		long long s=io::G();
		
		if(n<=k){
			puts("1");
			continue;
		}
		if((s-1)%(2*k)>=k){
			puts("0");
			continue;
		}
		int x=(s-1)/(2*k);
		if(x==0){
			printf("%lld\n",F(n));
		}
		else{
			long long v1=F(n-x-1),v2=F(n-x),v3=F(n-x+1);
			if(v2>v1&&v2>v3){
				printf("%lld\n",dmax(v1,v3));
			}
			else{
				printf("%lld\n",v2);
			}
		}
	}
	return 0;
}