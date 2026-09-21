/* Offline original-model viewer. No network requests, libraries or telemetry. */
'use strict';
(()=>{
  const $=id=>document.getElementById(id),canvas=$('model');
  try {
    const d=window.BLOODFANG_MODEL;
    if(!d)throw Error('The model data is missing. Extract the complete preview folder, then reopen this page.');
    const gl=canvas.getContext('webgl',{alpha:true,antialias:true,preserveDrawingBuffer:true});
    if(!gl)throw Error('This browser could not start WebGL. Open the GLB model in Blender or another 3D viewer.');
    const vertex=`attribute vec3 aPos,aNormal,aColor; attribute vec2 aUV; uniform mat4 uView; varying vec3 color,normal; varying vec2 uv;
      void main(){color=aColor;normal=aNormal;uv=aUV;gl_Position=uView*vec4(aPos,1.0);}`;
    const fragment=`precision mediump float; varying vec3 color,normal; varying vec2 uv; uniform sampler2D uTexture; uniform bool uTextured;
      void main(){vec3 n=normalize(normal);float key=max(0.0,dot(n,normalize(vec3(-.6,-.7,1.0))));
      float fill=max(0.0,dot(n,normalize(vec3(.8,-.4,.35))));float rim=max(0.0,dot(n,normalize(vec3(.2,.7,.6))));
      vec3 base=uTextured?pow(texture2D(uTexture,uv).rgb,vec3(2.2)):color;
      vec3 lit=base*(.35+key*.95+fill*.32)+base*vec3(.5,.10,.13)*rim;
      gl_FragColor=vec4(pow(clamp(lit,0.0,1.0),vec3(1.0/2.2)),1.0);}`;
    function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
      if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;}
    const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Could not link preview shaders.');
    gl.useProgram(program);gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
    const verts=d.vertices,positions=new Float32Array(verts.length*3),normals=new Float32Array(verts.length*3),colors=new Float32Array(verts.length*3);
    if(verts.length>65535)throw Error('Preview mesh exceeds its index capacity.');
    const indices=new Uint16Array(d.triangles.flatMap(t=>t.vertices));
    for(const t of d.triangles)for(const i of t.vertices)colors.set(d.materials[t.material].base_color.slice(0,3),i*3);
    function attribute(name,data,dynamic,size=3){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);
      gl.bufferData(gl.ARRAY_BUFFER,data,dynamic?gl.DYNAMIC_DRAW:gl.STATIC_DRAW);
      const a=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,size,gl.FLOAT,false,0,0);return b;}
    const posBuffer=attribute('aPos',positions,true),normalBuffer=attribute('aNormal',normals,true);
    attribute('aColor',colors,false);const indexBuffer=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,indexBuffer);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);
    attribute('aUV',new Float32Array(verts.flatMap(v=>v.uv||[0,0])),false,2);
    const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([255,255,255,255]));
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    gl.uniform1i(gl.getUniformLocation(program,'uTexture'),0);
    if(d.texture){const source=new Image();source.onload=()=>{gl.bindTexture(gl.TEXTURE_2D,texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,d.texture.uv_origin==='bottom_left');
      gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,gl.NONE);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,source);
      gl.uniform1i(gl.getUniformLocation(program,'uTextured'),1);
      if(window.BLOODFANG_VIEWER)window.BLOODFANG_VIEWER.textureReady=true;};
      source.onerror=()=>{$('error').hidden=false;$('error').textContent='The original texture could not load.';};source.src=d.texture.data_url;}
    const viewUniform=gl.getUniformLocation(program,'uView');
    function mul(a,b){let r=new Float32Array(16);for(let i=0;i<4;i++)for(let j=0;j<4;j++)for(let k=0;k<4;k++)r[i*4+j]+=a[i*4+k]*b[k*4+j];return r;}
    const inv=Object.fromEntries(d.bones.map(b=>[b.name,b.inverse_bind_matrix]));
    const skin=new Map();let poseIndex=-1,poseBlend=-1,poseAction=-1;
    function deform(action,time){const frames=action.keyframes,q=Math.min(frames.length-1,time*action.fps),a=Math.floor(q),b=Math.min(a+1,frames.length-1),blend=q-a;
      if(poseIndex===a&&poseBlend===blend&&poseAction===clipIndex)return;
      poseIndex=a;poseBlend=blend;poseAction=clipIndex;
      for(const bone of d.bones){const m=frames[a].bones[bone.name].world_pose_matrix,n=frames[b].bones[bone.name].world_pose_matrix;
        skin.set(bone.name,mul(m.map((v,i)=>v+(n[i]-v)*blend),inv[bone.name]));}
      for(let i=0;i<verts.length;i++){const v=verts[i],p=v.position,n=v.normal;let x=0,y=0,z=0,nx=0,ny=0,nz=0;
        for(const influence of v.weights){const m=skin.get(influence.bone),w=influence.weight;
          x+=(m[0]*p[0]+m[1]*p[1]+m[2]*p[2]+m[3])*w;y+=(m[4]*p[0]+m[5]*p[1]+m[6]*p[2]+m[7])*w;z+=(m[8]*p[0]+m[9]*p[1]+m[10]*p[2]+m[11])*w;
          nx+=(m[0]*n[0]+m[1]*n[1]+m[2]*n[2])*w;ny+=(m[4]*n[0]+m[5]*n[1]+m[6]*n[2])*w;nz+=(m[8]*n[0]+m[9]*n[1]+m[10]*n[2])*w;}
        positions[i*3]=x;positions[i*3+1]=y;positions[i*3+2]=z;normals[i*3]=nx;normals[i*3+1]=ny;normals[i*3+2]=nz;}
      gl.bindBuffer(gl.ARRAY_BUFFER,posBuffer);gl.bufferSubData(gl.ARRAY_BUFFER,0,positions);
      gl.bindBuffer(gl.ARRAY_BUFFER,normalBuffer);gl.bufferSubData(gl.ARRAY_BUFFER,0,normals);
    }
    function unit(v){const l=Math.hypot(...v)||1;return v.map(x=>x/l);}function cross(a,b){return[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];}function dot(a,b){return a.reduce((sum,x,i)=>sum+x*b[i],0);}
    let yaw=.58,pitch=.24,zoom=1,clipIndex=0,time=0,playing=!matchMedia('(prefers-reduced-motion: reduce)').matches,last=0;
    function camera(){const aspect=canvas.width/canvas.height,span=Math.max(5.8,6.7/aspect)*zoom;
      const target=[0,.2,1.7],radius=12,eye=[Math.sin(yaw)*Math.cos(pitch)*radius,-Math.cos(yaw)*Math.cos(pitch)*radius,target[2]+Math.sin(pitch)*radius];
      const back=unit(eye.map((v,i)=>v-target[i])),right=unit(cross([0,0,1],back)),up=cross(back,right);
      const view=[...right,-dot(right,eye),...up,-dot(up,eye),...back,-dot(back,eye),0,0,0,1];
      const ortho=[2/(span*aspect),0,0,0,0,2/span,0,0,0,0,-2/50,-1,0,0,0,1];
      const m=mul(ortho,view),transposed=new Float32Array(16);for(let r=0;r<4;r++)for(let c=0;c<4;c++)transposed[c*4+r]=m[r*4+c];return transposed;}
    d.actions.forEach((a,i)=>{const o=document.createElement('option');o.value=i;o.textContent=a.name==='Move'?'Flying':a.name;$('clip').append(o);});
    function playLabel(){$('play').textContent=playing?'Pause':'Play';$('play').setAttribute('aria-pressed',String(playing));}
    $('play').onclick=()=>{playing=!playing;playLabel();};playLabel();
    $('clip').onchange=()=>{clipIndex=Number($('clip').value);time=0;poseAction=-1;};
    $('timeline').oninput=()=>{const a=d.actions[clipIndex];time=Number($('timeline').value)/1000*(a.keyframes.length-1)/a.fps;playing=false;playLabel();};
    $('reset').onclick=()=>{yaw=.58;pitch=.24;zoom=1;};
    let drag=null;canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};
    canvas.onpointermove=e=>{if(drag){yaw+=(e.clientX-drag[0])*.008;pitch=Math.max(-.6,Math.min(1.2,pitch+(e.clientY-drag[1])*.006));drag=[e.clientX,e.clientY];}};
    canvas.onpointerup=canvas.onpointercancel=()=>{drag=null;};
    canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.65,Math.min(1.8,zoom*Math.exp(e.deltaY*.001)));},{passive:false});
    canvas.onkeydown=e=>{let used=true;if(e.key==='ArrowLeft')yaw-=.12;else if(e.key==='ArrowRight')yaw+=.12;else if(e.key==='ArrowUp')pitch=Math.min(1.2,pitch+.10);else if(e.key==='ArrowDown')pitch=Math.max(-.6,pitch-.10);else if(e.key==='+')zoom=Math.max(.65,zoom*.9);else if(e.key==='-')zoom=Math.min(1.8,zoom*1.1);else used=false;if(used)e.preventDefault();};
    function draw(now){const delta=last?Math.min(.10,(now-last)/1000):0;last=now;
      const ratio=Math.min(2,devicePixelRatio||1),w=Math.round(canvas.clientWidth*ratio),h=Math.round(canvas.clientHeight*ratio);
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
      const action=d.actions[clipIndex],duration=(action.keyframes.length-1)/action.fps;
      if(playing){time+=delta*Number($('speed').value);if(time>duration){if(action.loop||action.name==='Happy'||action.name==='Angry')time%=duration;else{time=duration;playing=false;playLabel();}}}
      deform(action,time);$('timeline').value=Math.round(time/duration*1000);$('frame').textContent=`${action.name} · ${Math.round(time*action.fps)+1}/${action.keyframes.length}`;
      gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniformMatrix4fv(viewUniform,false,camera());gl.drawElements(gl.TRIANGLES,indices.length,gl.UNSIGNED_SHORT,0);
    }
    function render(now){if(document.hidden)last=now;else draw(now);requestAnimationFrame(render);}
    window.BLOODFANG_VIEWER={ready:true,vertices:verts.length,triangles:indices.length/3,animations:d.actions.map(a=>a.name),renderCurrentFrame:()=>draw(last||performance.now())};
    requestAnimationFrame(render);
  }catch(error){$('error').hidden=false;$('error').textContent=error.message;window.BLOODFANG_VIEWER={ready:false,error:error.message};}
})();
