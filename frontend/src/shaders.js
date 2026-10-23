export const vertex = `uniform float pointSize; uniform float time; uniform float audio; uniform float intensity; varying vec3 vNormal; varying vec3 vPosition;
float wave(vec3 p){return sin(p.x*7.+time*1.3)*sin(p.y*6.-time)*cos(p.z*8.+time*.8);}
void main(){vNormal=normalize(normalMatrix*normal);vec3 p=position+normal*(wave(position)*(.025+audio*.19+intensity*.025));vec4 mv=modelViewMatrix*vec4(p,1.);vPosition=-mv.xyz;gl_Position=projectionMatrix*mv;gl_PointSize=pointSize*(2.4+audio*3.)*(5./max(1.,-mv.z));}`;
export const fragment = `uniform float time;uniform float intensity;uniform float audio; varying vec3 vNormal;varying vec3 vPosition;void main(){float f=pow(1.-abs(dot(normalize(vNormal),normalize(vPosition))),2.);vec3 c=mix(vec3(.005,.08,.16),vec3(.05,.75,1.),f);gl_FragColor=vec4(c*(1.+audio+intensity*.35),.12+f*.55);}`;
export const pointFragment = `uniform float intensity;uniform float time;void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;gl_FragColor=vec4(.2,.8,1.,(1.-d*2.)*(.5+intensity*.15+.1*sin(time*1.5)));}`;

export const wireFragment = `uniform float time;varying vec3 vPosition;void main(){float scan=pow(.5+.5*sin(vPosition.y*9.-time*1.5),8.);gl_FragColor=vec4(.05,.65,.9,.09+scan*.23);}`;
