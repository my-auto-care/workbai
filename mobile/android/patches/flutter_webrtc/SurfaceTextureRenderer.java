package com.cloudwebrtc.webrtc;

import android.graphics.SurfaceTexture;
import android.view.Surface;

import org.webrtc.EglBase;
import org.webrtc.EglRenderer;
import org.webrtc.GlRectDrawer;
import org.webrtc.RendererCommon;
import org.webrtc.ThreadUtils;
import org.webrtc.VideoFrame;

import java.util.concurrent.CountDownLatch;

import io.flutter.view.TextureRegistry;

public class SurfaceTextureRenderer extends EglRenderer {
  private RendererCommon.RendererEvents rendererEvents;
  private final Object layoutLock = new Object();
  private boolean isRenderingPaused;
  private boolean isFirstFrameRendered;
  private int rotatedFrameWidth;
  private int rotatedFrameHeight;
  private int frameRotation;

  public SurfaceTextureRenderer(String name) {
    super(name);
  }

  public void init(final EglBase.Context sharedContext,
                   RendererCommon.RendererEvents rendererEvents) {
    init(sharedContext, rendererEvents, EglBase.CONFIG_PLAIN, new GlRectDrawer());
  }

  public void init(final EglBase.Context sharedContext,
                   RendererCommon.RendererEvents rendererEvents, final int[] configAttributes,
                   RendererCommon.GlDrawer drawer) {
    ThreadUtils.checkIsOnMainThread();
    this.rendererEvents = rendererEvents;
    synchronized (layoutLock) {
      isFirstFrameRendered = false;
      rotatedFrameWidth = 0;
      rotatedFrameHeight = 0;
      frameRotation = -1;
    }
    super.init(sharedContext, configAttributes, drawer);
  }

  @Override
  public void init(final EglBase.Context sharedContext, final int[] configAttributes,
                   RendererCommon.GlDrawer drawer) {
    init(sharedContext, null, configAttributes, drawer);
  }

  @Override
  public void setFpsReduction(float fps) {
    synchronized (layoutLock) {
      isRenderingPaused = fps == 0f;
    }
    super.setFpsReduction(fps);
  }

  @Override
  public void disableFpsReduction() {
    synchronized (layoutLock) {
      isRenderingPaused = false;
    }
    super.disableFpsReduction();
  }

  @Override
  public void pauseVideo() {
    synchronized (layoutLock) {
      isRenderingPaused = true;
    }
    super.pauseVideo();
  }

  @Override
  public void onFrame(VideoFrame frame) {
    if (surface == null) {
      producer.setSize(frame.getRotatedWidth(), frame.getRotatedHeight());
      surface = producer.getSurface();
      createEglSurface(surface);
    }
    updateFrameDimensionsAndReportEvents(frame);
    super.onFrame(frame);
  }

  private Surface surface = null;
  private TextureRegistry.SurfaceProducer producer;

  public void surfaceCreated(final TextureRegistry.SurfaceProducer producer) {
    ThreadUtils.checkIsOnMainThread();
    this.producer = producer;
    this.producer.setCallback(
        new TextureRegistry.SurfaceProducer.Callback() {
          @Override
          public void onSurfaceAvailable() {
          }

          @Override
          public void onSurfaceCleanup() {
            surfaceDestroyed();
          }
        }
    );
  }

  public void surfaceDestroyed() {
    ThreadUtils.checkIsOnMainThread();
    final CountDownLatch completionLatch = new CountDownLatch(1);
    releaseEglSurface(completionLatch::countDown);
    ThreadUtils.awaitUninterruptibly(completionLatch);
    surface = null;
  }

  private void updateFrameDimensionsAndReportEvents(VideoFrame frame) {
    synchronized (layoutLock) {
      if (isRenderingPaused) return;
      if (!isFirstFrameRendered) {
        isFirstFrameRendered = true;
        if (rendererEvents != null) rendererEvents.onFirstFrameRendered();
      }
      if (rotatedFrameWidth != frame.getRotatedWidth()
          || rotatedFrameHeight != frame.getRotatedHeight()
          || frameRotation != frame.getRotation()) {
        rotatedFrameWidth = frame.getRotatedWidth();
        rotatedFrameHeight = frame.getRotatedHeight();
        frameRotation = frame.getRotation();
        if (rendererEvents != null) {
          rendererEvents.onFrameResolutionChanged(
              frame.getRotatedWidth(), frame.getRotatedHeight(), frame.getRotation());
        }
      }
    }
  }
}
